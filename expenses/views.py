import json
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import make_aware
from .scraper import extrair_dados_nfce
from .models import Establishment, Product, Receipt, ReceiptItem
from .leitor_email import processar_emails

@login_required
def home(request):
    return render(request, 'home.html')

@login_required
def ler_nota(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            url = data.get('url')
            
            if not url:
                return JsonResponse({'sucesso': False, 'mensagem': 'URL não fornecida.'})
                
            dados = extrair_dados_nfce(url)
            
            if not dados or not dados.get('chave_acesso'):
                return JsonResponse({'sucesso': False, 'mensagem': 'Erro ao extrair dados ou chave não encontrada.'})
            
            if dados.get('data_emissao'):
                dados['data_emissao_str'] = dados['data_emissao'].strftime("%d/%m/%Y %H:%M")

            chave = dados['chave_acesso']
            if Receipt.objects.filter(access_key=chave).exists():
                return JsonResponse({
                    'sucesso': False,
                    'mensagem': 'Esta nota já foi cadastrada!',
                    'dados': dados
                })

            # Busca ou cria o estabelecimento
            if dados['cnpj']:
                est, _ = Establishment.objects.get_or_create(
                    cnpj=dados['cnpj'],
                    defaults={'name': dados['estabelecimento'], 'address': dados['endereco']}
                )
            else:
                est, _ = Establishment.objects.get_or_create(name=dados['estabelecimento'])
            
            total_nota = sum(float(item['preco_total']) for item in dados['itens'])
            data_compra = make_aware(dados['data_emissao']) if dados['data_emissao'] else None
            
            nota = Receipt.objects.create(
                user=request.user, establishment=est, issue_date=data_compra,
                total_amount=total_nota, access_key=chave
            )
            
            for item in dados['itens']:
                produto, _ = Product.objects.get_or_create(name=item['nome'])
                ReceiptItem.objects.create(
                    receipt=nota, product=produto, quantity=item['quantidade'],
                    unit_price=item['preco_unitario'], total_price=item['preco_total']
                )
                
            return JsonResponse({
                'sucesso': True,
                'mensagem': 'Nota salva com sucesso!',
                'dados': dados
            })

        except Exception as e:
            return JsonResponse({'sucesso': False, 'mensagem': f'Erro no servidor: {str(e)}'})

    # Requisição GET retorna apenas o HTML
    return render(request, 'expenses/ler_nota.html')

@login_required
def sincronizar_email(request):
    try:
        total = processar_emails()
        return JsonResponse({'sucesso': True, 'mensagem': f'Sincronização concluída! {total} novas notas.'})
    except Exception as e:
        return JsonResponse({'sucesso': False, 'mensagem': f'Erro: {str(e)}'})