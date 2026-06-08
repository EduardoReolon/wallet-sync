import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

def extrair_dados_nfe(url=None, html_content=None):
    """
    Extrai dados da nota fiscal. 
    Pode receber a URL (e baixar o HTML) ou o html_content já pronto.
    """
    if html_content:
        # Se veio o HTML pronto (ex: do plugin do Chrome), não precisamos gastar requisição
        soup = BeautifulSoup(html_content, 'html.parser')
    elif url:
        # Se veio só a URL (ex: do leitor de QR Code), o backend vai lá e busca
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
    else:
        # Se não enviou nenhum dos dois, não tem o que fazer
        return None

    # Ramificação para decidir qual extrator usar
    if soup.find('div', id='NFe') or soup.find('div', class_='GeralXslt'):
        return extrair_nfe(soup)
    else:
        return extrair_nfce(soup)

def extrair_nfe(soup):
    """Função auxiliar para extrair dados do HTML padrão de NF-e da SEFAZ"""
    
    # Função utilitária para buscar um span logo após um label específico
    def buscar_por_label(texto_label, elemento_pai=soup):
        label = elemento_pai.find(lambda tag: tag.name == 'label' and texto_label in tag.text)
        if label:
            span = label.find_next_sibling('span')
            if span:
                return span.text.strip()
        return None

    # Chave de Acesso
    chave_acesso = buscar_por_label('Chave de Acesso')
    if chave_acesso:
        chave_acesso = chave_acesso.replace(' ', '')
        
    # Dados do Emitente
    div_emitente = soup.find('div', id='Emitente')
    nome_estabelecimento = buscar_por_label('Nome / Razão Social', div_emitente) if div_emitente else "Desconhecido"
    cnpj = buscar_por_label('CNPJ', div_emitente) if div_emitente else None
    
    # Endereço (concatenando rua, bairro, etc, se necessário)
    endereco = buscar_por_label('Endereço', div_emitente) if div_emitente else None
    
    # Data de Emissão
    data_emissao = None
    data_str = buscar_por_label('Data de Emissão')
    if data_str:
        # Ex: '26/05/2026 10:10:42-03:00' -> remove o fuso horário para o datetime padrão
        data_limpa = data_str.split('-')[0].strip()
        try:
            data_emissao = datetime.strptime(data_limpa, "%d/%m/%Y %H:%M:%S")
        except ValueError:
            pass

    # Total da Nota
    total_nf = 0.0
    div_totais = soup.find('div', id='Totais')
    if div_totais:
        texto_total = buscar_por_label('Valor Total da NFe', div_totais)
        if texto_total:
            total_nf = float(texto_total.replace('.', '').replace(',', '.'))

    # Itens (Produtos)
    itens = []
    div_prod = soup.find('div', id='Prod')
    
    if div_prod:
        # As linhas de produtos alternam entre a tabela de resumo (toggle) e os detalhes (toggable)
        tabelas_resumo = div_prod.find_all('table', class_='toggle box')
        tabelas_detalhe = div_prod.find_all('table', class_='toggable box')
        
        for resumo, detalhe in zip(tabelas_resumo, tabelas_detalhe):
            try:
                td_desc = resumo.find('td', class_='fixo-prod-serv-descricao')
                nome = td_desc.find('span').text.strip() if td_desc else "Sem nome"
                
                td_qtd = resumo.find('td', class_='fixo-prod-serv-qtd')
                qtd_str = td_qtd.find('span').text.strip().replace(',', '.') if td_qtd else "1.0"
                
                td_valor = resumo.find('td', class_='fixo-prod-serv-vb')
                vl_total_str = td_valor.find('span').text.strip().replace('.', '').replace(',', '.') if td_valor else "0.0"
                
                # O preço unitário real fica na tabela de detalhes
                vl_unit_str = buscar_por_label('Valor unitário de comercialização', detalhe)
                if not vl_unit_str:
                    vl_unit_str = "0.0"
                else:
                    vl_unit_str = vl_unit_str.replace('.', '').replace(',', '.')
                
                # Código de barras (EAN/GTIN)
                codigo_barras = buscar_por_label('Código EAN Comercial', detalhe)
                if codigo_barras and codigo_barras.upper() == "SEM GTIN":
                    codigo_barras = ""

                itens.append({
                    'codigo': codigo_barras,
                    'nome': nome,
                    'quantidade': float(qtd_str),
                    'preco_unitario': float(vl_unit_str),
                    'preco_total': float(vl_total_str)
                })
            except Exception:
                continue

    return {
        'chave_acesso': chave_acesso,
        'cancelada': False,  # Opcional: buscar por "CANCELADA" no HTML
        'estabelecimento': nome_estabelecimento,
        'cnpj': cnpj,
        'endereco': endereco,
        'data_emissao': data_emissao,
        'total_nota': total_nf,
        'itens': itens
    }

def extrair_nfce(soup):
    """Sua lógica original para NFC-e vem aqui"""
    # Estabelecimento
    nome_estabelecimento = soup.find('div', id='u20').text.strip() if soup.find('div', id='u20') else "Desconhecido"
    
    # CNPJ e Endereço
    text_divs = soup.find_all('div', class_='text')
    cnpj = text_divs[0].text.replace('CNPJ:', '').strip() if len(text_divs) > 0 else None
    endereco = " ".join(text_divs[1].text.split()) if len(text_divs) > 1 else None

    # Chave e Data
    chave_acesso = soup.find('span', class_='chave').text.replace(' ', '').strip() if soup.find('span', class_='chave') else ""
    
    data_emissao = None
    texto_geral = soup.get_text()
    match_data = re.search(r'Emissão:\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})', texto_geral)
    if match_data:
        data_emissao = datetime.strptime(match_data.group(1), "%d/%m/%Y %H:%M:%S")

    # Itens
    itens = []
    total_nf = 0.0
    linhas_produtos = soup.find_all('tr', id=lambda x: x and x.startswith('Item +'))
    for linha in linhas_produtos:
        try:
            nome = linha.find('span', class_='txtTit2').text.strip()
            span_codigo = linha.find('span', class_='RCod')
            codigo_barras = ""
            if span_codigo:
                cod_limpo = span_codigo.text.replace('(Código:', '').replace(')', '').strip()
                codigo_barras = cod_limpo if cod_limpo.upper() != "SEM GTIN" else ""

            qtd_str = linha.find('span', class_='Rqtd').text.replace('Qtde.:', '').strip().replace(',', '.')
            vl_unit_str = linha.find('span', class_='RvlUnit').text.replace('Vl. Unit.:', '').strip().replace(',', '.')
            vl_total_str = linha.find('span', class_='valor').text.strip().replace(',', '.')

            try:
                qtd = float(qtd_str)
                vl_unit = float(vl_unit_str)
                vl_total = float(vl_total_str)
            except ValueError:
                qtd, vl_unit, vl_total = 1.0, 0.0, 0.0

            total_nf += vl_total

            itens.append({
                'codigo': codigo_barras,
                'nome': nome, 
                'quantidade': qtd, 
                'preco_unitario': vl_unit, 
                'preco_total': vl_total
            })
        except AttributeError:
            continue

    span_total = soup.find('span', class_='totalNumb txtMax')
    if span_total:
        try:
            texto_valor = span_total.text.strip().replace('.', '').replace(',', '.')
            total_nf = float(texto_valor)
        except ValueError:
            pass

    return {
        'chave_acesso': chave_acesso,
        'cancelada': False,
        'estabelecimento': nome_estabelecimento,
        'cnpj': cnpj,
        'endereco': endereco,
        'data_emissao': data_emissao,
        'total_nota': round(total_nf, 2),
        'itens': itens
    }