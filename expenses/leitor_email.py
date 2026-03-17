import os
import sys
import django
import imaplib
import email
import xml.etree.ElementTree as ET
from datetime import datetime
from django.utils.timezone import make_aware, is_aware
from dotenv import load_dotenv
import email.utils

# 1. Configuração de Caminhos e Django
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
load_dotenv(os.path.join(BASE_DIR, '.env'))
django.setup()

# IMPORTANTE: Use get_user_model para não dar erro com seu CustomUser
from django.contrib.auth import get_user_model
from expenses.models import Establishment, Product, Receipt, ReceiptItem

User = get_user_model()

# 2. Configurações de E-mail
EMAIL_USER = os.getenv('EMAIL')
EMAIL_PASS = os.getenv('EMAIL_SENHA')
SERVIDOR_IMAP = 'imap.gmail.com'

def salvar_xml_no_banco(xml_content, user):
    try:
        root = ET.fromstring(xml_content)
        ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}

        # Identificação e Chave
        infNFe = root.find('.//ns:infNFe', ns)
        if infNFe is None: return "XML inválido: infNFe não encontrada."
        
        chave = infNFe.attrib['Id'].replace('NFe', '')
        
        if Receipt.objects.filter(access_key=chave).exists():
            return f"Ignorada: Nota {chave} já existe."

        ide = root.find('.//ns:ide', ns)
        data_emissao = ide.find('ns:dhEmi', ns).text
        data_dt = datetime.fromisoformat(data_emissao)

        # Se a data do XML não tiver fuso (naive), a gente força o do Django
        # Se já tiver (aware), deixamos como está
        if not is_aware(data_dt):
            data_dt = make_aware(data_dt)

        # Estabelecimento (Emitente)
        emit = root.find('.//ns:emit', ns)
        cnpj = emit.find('ns:CNPJ', ns).text
        nome = emit.find('ns:xNome', ns).text
        est, _ = Establishment.objects.get_or_create(cnpj=cnpj, defaults={'name': nome})

        # Valor Total
        total_val = float(root.find('.//ns:vNF', ns).text)
        
        nota = Receipt.objects.create(
            user=user, 
            establishment=est, 
            issue_date=data_dt,
            total_amount=total_val, 
            access_key=chave
        )

        # Itens da Nota
        for det in root.findall('.//ns:det', ns):
            prod_xml = det.find('ns:prod', ns)
            nome_item = prod_xml.find('ns:xProd', ns).text
            
            # Busca o EAN (Código de barras)
            ean_xml = prod_xml.find('ns:cEAN', ns)
            ean_val = ean_xml.text if ean_xml is not None else ""

            # Lógica Híbrida: Se tem EAN válido, busca/cria por ele. Se não, vai pelo nome.
            if ean_val and ean_val.upper() != "SEM GTIN":
                produto, _ = Product.objects.get_or_create(
                    barcode=ean_val, 
                    defaults={'name': nome_item} # Salva o nome só se estiver criando agora
                )
            else:
                produto, _ = Product.objects.get_or_create(name=nome_item)
            
            ReceiptItem.objects.create(
                receipt=nota, 
                product=produto,
                quantity=float(prod_xml.find('ns:qCom', ns).text),
                unit_price=float(prod_xml.find('ns:vUnCom', ns).text),
                total_price=float(prod_xml.find('ns:vProd', ns).text)
            )
        return f"Sucesso: Nota {chave} importada."
    except Exception as e:
        return f"Erro ao processar XML: {e}"

def processar_emails():
    print("Iniciando varredura de e-mails...")

    pastas = ['INBOX', '"[Gmail]/Spam"']
    mail = imaplib.IMAP4_SSL(SERVIDOR_IMAP)
    notas_importadas = 0
    
    try:
        mail.login(EMAIL_USER, EMAIL_PASS)
        for pasta in pastas:
            status, _ = mail.select(pasta)
            if status != 'OK': continue

            _, mensagens = mail.search(None, 'UNSEEN')
            
            for id_email in mensagens[0].split():
                _, msg_dados = mail.fetch(id_email, '(RFC822)')
                msg = email.message_from_bytes(msg_dados[0][1])
                
                # 1. Extrai o e-mail real do remetente (ex: tira de "Nome <email@dominio.com>")
                remetente_bruto = msg.get('From')
                _, email_remetente = email.utils.parseaddr(remetente_bruto)
                
                # 2. Busca o usuário pelo e-mail
                usuario = User.objects.filter(email=email_remetente).first()
                
                # 3. Se não existir, pega ou cria a conta genérica
                if not usuario:
                    usuario, criado = User.objects.get_or_create(
                        email='sistema@wallet-sync.local'
                    )
                    if criado:
                        usuario.set_unusable_password() # Bloqueia login com senha
                        usuario.save()
                
                # 4. Processa os anexos daquele e-mail
                for part in msg.walk():
                    if part.get_filename() and part.get_filename().lower().endswith('.xml'):
                        xml_data = part.get_payload(decode=True)
                        resultado = salvar_xml_no_banco(xml_data, usuario)
                        print(f"[{email_remetente}] {resultado}")
                        
                        if "Sucesso" in resultado:
                            notas_importadas += 1
                            
        return notas_importadas
    finally:
        mail.logout()

if __name__ == '__main__':
    processar_emails()