import json
import xml.etree.ElementTree as ET
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import make_aware, is_aware
from .scraper import extrair_dados_nfe
from .models import Establishment, Product, Receipt, ReceiptItem
from .leitor_email import processar_emails
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from .utils import extrair_dados_xml, salvar_nota_banco

User = get_user_model()

@login_required
def home(request):
    return render(request, 'home.html')

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.timezone import make_aware

# Importe seus modelos aqui
from .models import Establishment, Product, Receipt, ReceiptItem 

@login_required
def ler_nota(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            url = data.get('url')
            xml_content = data.get('xml')
            
            dados = None
            
            if url:
                dados = extrair_dados_nfe(url) 
            elif xml_content:
                dados = extrair_dados_xml(xml_content)

            if not dados or not dados.get('chave_acesso'):
                return JsonResponse({'sucesso': False, 'mensagem': 'Erro ao extrair dados ou chave não encontrada.'})

            # CORREÇÃO AQUI: 
            # 1. Recebe a tupla (booleano, string)
            sucesso, mensagem = salvar_nota_banco(dados, request.user)
            
            # 2. Converte para uma resposta JSON válida para o navegador
            return JsonResponse({
                'sucesso': sucesso, 
                'mensagem': mensagem, 
                'dados': dados
            })

        except Exception as e:
            return JsonResponse({'sucesso': False, 'mensagem': f'Erro no servidor: {str(e)}'})

    return render(request, 'expenses/ler_nota.html')

@csrf_exempt
@login_required
def ler_notas_lote(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Prepara uma lista única de itens para processar, unificando os dois mundos
            itens_para_processar = []
            
            # 1. Pega o formato NOVO do plugin (Array de objetos com {url, html})
            if 'notas' in data:
                itens_para_processar.extend(data['notas'])
                
            # 2. Pega o formato ANTIGO (Array de strings de URLs, caso ainda seja usado aqui)
            if 'urls' in data:
                for u in data['urls']:
                    itens_para_processar.append({'url': u, 'html': None})
            
            cont_sucesso = 0
            cont_erro = 0
            detalhes_erros = []

            for item in itens_para_processar:
                # Extrai do dicionário, suportando ambos os casos
                url_atual = item.get('url')
                html_atual = item.get('html')
                
                try:
                    # Passamos os dois parâmetros. A função sabe o que fazer!
                    dados = extrair_dados_nfe(url=url_atual, html_content=html_atual)
                    
                    if not dados or not dados.get('chave_acesso'):
                        cont_erro += 1
                        detalhes_erros.append(f"Chave não encontrada na URL: {url_atual}")
                        continue

                    # Utiliza a sua lógica atual de salvamento
                    sucesso, mensagem = salvar_nota_banco(dados, request.user)
                    
                    if sucesso:
                        cont_sucesso += 1
                    else:
                        cont_erro += 1
                        detalhes_erros.append(f"Erro ao salvar ({url_atual}): {mensagem}")

                except Exception as e_item:
                    cont_erro += 1
                    detalhes_erros.append(f"Falha ao processar ({url_atual}): {str(e_item)}")

            return JsonResponse({
                'sucesso': True,
                'sucessos': cont_sucesso,
                'erros': cont_erro,
                'detalhes_erros': detalhes_erros
            })

        except Exception as e:
            return JsonResponse({'sucesso': False, 'mensagem': f'Erro crítico no servidor: {str(e)}'}, status=500)

    return JsonResponse({'erro': 'Método não permitido'}, status=405)

@csrf_exempt
def ler_nota_iphone(request):
    if request.method == 'POST':
        try:
            dados_req = json.loads(request.body)
            url_nota = dados_req.get('url')
            email_usuario = dados_req.get('email')

            if not url_nota:
                return JsonResponse({'sucesso': False, 'mensagem': 'URL ausente.'}, status=400)

            # Busca o usuário ou cai para o genérico do sistema
            usuario = User.objects.filter(email=email_usuario).first()
            vinculado_usuario = True

            if not usuario:
                usuario, criado = User.objects.get_or_create(
                    email='sistema@wallet-sync.local'
                )
                if criado:
                    usuario.set_unusable_password() # Bloqueia login com senha
                    usuario.save()
                vinculado_usuario = False

            # 1. Extrai os dados
            dados = extrair_dados_nfe(url_nota)

            # 2. Verifica duplicidade
            chave = dados.get('chave_acesso')
            if Receipt.objects.filter(access_key=chave).exists():
                return JsonResponse({'sucesso': False, 'mensagem': 'Essa nota já foi registrada.'})

            # 3. Estabelecimento
            est, _ = Establishment.objects.get_or_create(
                cnpj=dados['cnpj'],
                defaults={'name': dados['estabelecimento']}
            )

            # 4. Data
            data_emissao = dados.get('data_emissao')
            if data_emissao and not is_aware(data_emissao):
                data_emissao = make_aware(data_emissao)

            total_nota = sum(float(item['preco_total']) for item in dados['itens'])

            # 5. Salva a Nota
            nota = Receipt.objects.create(
                user=usuario,
                establishment=est,
                issue_date=data_emissao,
                total_amount=total_nota,
                access_key=chave
            )

            # 6. Salva os Itens
            for item in dados['itens']:
                codigo_barras = item.get('codigo')
                
                if codigo_barras:
                    produto, _ = Product.objects.get_or_create(
                        barcode=codigo_barras,
                        defaults={'name': item['nome']}
                    )
                else:
                    produto, _ = Product.objects.get_or_create(name=item['nome'])

                ReceiptItem.objects.create(
                    receipt=nota, product=produto, quantity=float(item['quantidade']),
                    unit_price=float(item['preco_unitario']), total_price=float(item['preco_total'])
                )

            # 7. Retorno dinâmico
            if vinculado_usuario:
                mensagem_final = f'Salvo! R$ {total_nota:.2f} na sua conta.'
            else:
                mensagem_final = f'Salvo! R$ {total_nota:.2f} registrado apenas no sistema (sem vínculo de conta, verifique o e-mail cadastrado).'

            return JsonResponse({'sucesso': True, 'mensagem': mensagem_final})

        except Exception as e:
            return JsonResponse({'sucesso': False, 'mensagem': f'Erro: {str(e)}'}, status=400)

    return JsonResponse({'sucesso': False, 'mensagem': 'Método não permitido.'}, status=405)

@login_required
def sincronizar_email(request):
    try:
        total = processar_emails()
        return JsonResponse({'sucesso': True, 'mensagem': f'Sincronização concluída! {total} novas notas.'})
    except Exception as e:
        return JsonResponse({'sucesso': False, 'mensagem': f'Erro: {str(e)}'})