from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import make_aware
from .scraper import extrair_dados_nfce
from .models import Establishment, Product, Receipt, ReceiptItem

@login_required
def home(request):
    return render(request, 'home.html')

@login_required
def ler_nota(request):
    dados = None
    if request.method == 'POST':
        url = request.POST.get('url_nota')
        if url:
            dados = extrair_dados_nfce(url)
            
            if dados and dados.get('chave_acesso'):
                chave = dados['chave_acesso']
                
                if Receipt.objects.filter(access_key=chave).exists():
                    messages.warning(request, "Esta nota já foi cadastrada!")
                else:
                    # Busca ou cria o estabelecimento (prioriza CNPJ)
                    if dados['cnpj']:
                        est, _ = Establishment.objects.get_or_create(
                            cnpj=dados['cnpj'],
                            defaults={'name': dados['estabelecimento'], 'address': dados['endereco']}
                        )
                    else:
                        est, _ = Establishment.objects.get_or_create(name=dados['estabelecimento'])
                    
                    total_nota = sum(float(item['preco_total']) for item in dados['itens'])
                    
                    # Trata a data de emissão para incluir fuso horário
                    data_compra = make_aware(dados['data_emissao']) if dados['data_emissao'] else None
                    
                    nota = Receipt.objects.create(
                        user=request.user,
                        establishment=est,
                        issue_date=data_compra,
                        total_amount=total_nota,
                        access_key=chave
                    )
                    
                    for item in dados['itens']:
                        produto, _ = Product.objects.get_or_create(name=item['nome'])
                        ReceiptItem.objects.create(
                            receipt=nota, product=produto, quantity=item['quantidade'],
                            unit_price=item['preco_unitario'], total_price=item['preco_total']
                        )
                        
                    messages.success(request, "Nota salva com sucesso!")
            else:
                messages.error(request, "Erro ao extrair dados ou chave de acesso não encontrada.")

    return render(request, 'expenses/ler_nota.html', {'dados': dados})