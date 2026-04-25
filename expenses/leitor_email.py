import os
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
                
                for part in msg.walk():
                    if part.get_filename() and part.get_filename().lower().endswith('.xml'):
                        xml_data = part.get_payload(decode=True)
                        
                        # Processamento padronizado
                        dados = extrair_dados_xml(xml_data)
                        if dados:
                            sucesso, mensagem = salvar_nota_banco(dados, usuario)
                            print(f"[{email_remetente}] {mensagem}")
                            if sucesso:
                                notas_importadas += 1
                        else:
                            print(f"[{email_remetente}] Erro: XML em formato não reconhecido.")
                            
        return notas_importadas
    finally:
        mail.logout()

if __name__ == '__main__':
    processar_emails()