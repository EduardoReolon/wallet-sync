import html
import os
import re
import sys
import django
import imaplib
import email
from dotenv import load_dotenv
import email.utils


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
load_dotenv(os.path.join(BASE_DIR, '.env'))
django.setup()

from django.contrib.auth import get_user_model
# Importa as mesmas regras de negócio usadas pela Web
from expenses.utils import extrair_dados_xml, salvar_nota_banco
from .scraper import extrair_dados_nfce

User = get_user_model()
EMAIL_USER = os.getenv('EMAIL')
EMAIL_PASS = os.getenv('EMAIL_SENHA')
SERVIDOR_IMAP = 'imap.gmail.com'

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
                
                remetente_bruto = msg.get('From')
                _, email_remetente = email.utils.parseaddr(remetente_bruto)
                
                usuario = User.objects.filter(email=email_remetente).first()
                
                if not usuario:
                    usuario, criado = User.objects.get_or_create(
                        email='sistema@wallet-sync.local'
                    )
                    if criado:
                        usuario.set_unusable_password()
                        usuario.save()
                
                dados = None # Inicializa os dados da nota
                
                for part in msg.walk():
                    # 1. TENTA PRIMEIRO POR ANEXO XML
                    if part.get_filename() and part.get_filename().lower().endswith('.xml'):
                        xml_data = part.get_payload(decode=True)
                        dados = extrair_dados_xml(xml_data)
                        if dados:
                            break # Achou e extraiu, sai da busca no e-mail
                            
                    # 2. SE NÃO TEM XML, PROCURA NO CORPO HTML PELA URL
                    elif part.get_content_type() == "text/html":
                        html_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        
                        # Expressão regular para pegar link padrão Sefaz (.gov.br contendo 'nfce')
                        match_url = re.search(r'(https?://[^\s"\'<>]*?\.gov\.br/[^\s"\'<>]*?nfce[^\s"\'<>]*)', html_content, re.IGNORECASE)
                        
                        if match_url:
                            url_suja = match_url.group(1)
                            # html.unescape limpa coisas como &amp; que o Outlook/Gmail inserem
                            url_limpa = html.unescape(url_suja)
                            dados = extrair_dados_nfce(url_limpa)
                            if dados:
                                break # Achou e extraiu, sai da busca no e-mail

                # Processamento padronizado final (após o término do for walk)
                if dados:
                    sucesso, mensagem = salvar_nota_banco(dados, usuario)
                    print(f"[{email_remetente}] {mensagem}")
                    if sucesso:
                        notas_importadas += 1
                else:
                    print(f"[{email_remetente}] Erro: Nem XML nem URL válidos encontrados.")
                            
        return notas_importadas
    finally:
        mail.logout()

if __name__ == '__main__':
    processar_emails()