import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime

def extrair_dados_nfce(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Estabelecimento
    nome_estabelecimento = soup.find('div', id='u20').text.strip() if soup.find('div', id='u20') else "Desconhecido"
    
    # CNPJ e Endereço (geralmente nas divs com classe 'text' logo abaixo do nome)
    text_divs = soup.find_all('div', class_='text')
    cnpj = text_divs[0].text.replace('CNPJ:', '').strip() if len(text_divs) > 0 else None
    endereco = " ".join(text_divs[1].text.split()) if len(text_divs) > 1 else None

    # Chave e Data
    chave_acesso = soup.find('span', class_='chave').text.replace(' ', '').strip() if soup.find('span', class_='chave') else ""
    
    data_emissao = None
    texto_geral = soup.get_text()
    match_data = re.search(r'Emissão:\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})', texto_geral)
    if match_data:
        # Converte a string '16/03/2026 09:01:37' para um objeto datetime do Python
        data_emissao = datetime.strptime(match_data.group(1), "%d/%m/%Y %H:%M:%S")

    # Itens
    itens = []
    linhas_produtos = soup.find_all('tr', id=lambda x: x and x.startswith('Item +'))
    for linha in linhas_produtos:
        try:
            nome = linha.find('span', class_='txtTit2').text.strip()

            span_codigo = linha.find('span', class_='RCod')
            codigo_barras = ""
            if span_codigo:
                cod_limpo = span_codigo.text.replace('(Código:', '').replace(')', '').strip()
                # Ignora se for o padrão sem EAN
                codigo_barras = cod_limpo if cod_limpo.upper() != "SEM GTIN" else ""

            qtd = linha.find('span', class_='Rqtd').text.replace('Qtde.:', '').strip().replace(',', '.')
            vl_unit = linha.find('span', class_='RvlUnit').text.replace('Vl. Unit.:', '').strip().replace(',', '.')
            vl_total = linha.find('span', class_='valor').text.strip().replace(',', '.')

            itens.append({
                'nome': nome, 
                'codigo': codigo_barras,
                'quantidade': qtd, 
                'preco_unitario': vl_unit, 
                'preco_total': vl_total
            })
        except AttributeError:
            continue

    return {
        'estabelecimento': nome_estabelecimento,
        'cnpj': cnpj,
        'endereco': endereco,
        'chave_acesso': chave_acesso,
        'data_emissao': data_emissao,
        'itens': itens
    }