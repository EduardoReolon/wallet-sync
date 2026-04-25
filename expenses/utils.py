import xml.etree.ElementTree as ET
from datetime import datetime
from django.utils.timezone import make_aware, is_aware
from .models import Establishment, Product, Receipt, ReceiptItem

def extrair_dados_xml(xml_content):
    """ Extrai os dados validando o layout da Sefaz de forma segura """
    # Garante que o conteúdo seja lido corretamente, vindo de arquivo ou e-mail (bytes)
    if isinstance(xml_content, bytes):
        xml_string = xml_content.decode('utf-8', errors='ignore')
    else:
        xml_string = xml_content

    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError:
        return None

    ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
    
    infNFe = root.find('.//ns:infNFe', ns)
    if infNFe is None:
        return None

    def get_text(parent, tag):
        if parent is None: return None
        element = parent.find(tag, ns)
        return element.text if element is not None else None

    chave = infNFe.attrib.get('Id', '').replace('NFe', '')
    
    cStat_text = get_text(root, './/ns:protNFe/ns:infProt/ns:cStat')
    cancelada = cStat_text in ['101', '135', '151']

    emit = infNFe.find('ns:emit', ns)
    cnpj_cpf = get_text(emit, 'ns:CNPJ') or get_text(emit, 'ns:CPF')
    nome_est = get_text(emit, 'ns:xNome') or 'Estabelecimento Desconhecido'
    ender_est = get_text(emit, 'ns:enderEmit/ns:xLgr') or ''
    
    ide = infNFe.find('ns:ide', ns)
    data_emissao = get_text(ide, 'ns:dhEmi') or get_text(ide, 'ns:dEmi')
    
    itens = []
    for det in infNFe.findall('ns:det', ns):
        prod = det.find('ns:prod', ns)
        if prod is not None:
            cod_ean = get_text(prod, 'ns:cEAN')
            cod_prod = get_text(prod, 'ns:cProd')
            codigo = cod_ean if cod_ean and cod_ean.upper() != 'SEM GTIN' else cod_prod
            
            nome_prod = get_text(prod, 'ns:xProd') or 'Produto sem nome'
            
            try:
                qnt = float(get_text(prod, 'ns:qCom') or 0)
                v_unit = float(get_text(prod, 'ns:vUnCom') or 0)
                v_tot = float(get_text(prod, 'ns:vProd') or 0)
            except ValueError:
                qnt, v_unit, v_tot = 1.0, 0.0, 0.0
            
            itens.append({
                'codigo': codigo,
                'nome': nome_prod,
                'quantidade': qnt,
                'preco_unitario': v_unit,
                'preco_total': v_tot
            })

    # Pega o valor total da nota direto da tag vNF, se existir
    total_nf_text = get_text(infNFe, 'ns:total/ns:ICMSTot/ns:vNF')
    try:
        total_nf = float(total_nf_text) if total_nf_text else sum(i['preco_total'] for i in itens)
    except ValueError:
        total_nf = sum(i['preco_total'] for i in itens)

    return {
        'chave_acesso': chave,
        'cancelada': cancelada,
        'estabelecimento': nome_est,
        'cnpj': cnpj_cpf,
        'endereco': ender_est,
        'data_emissao': data_emissao,
        'total_nota': total_nf,
        'itens': itens
    }

def salvar_nota_banco(dados, user):
    """ Salva os dados no banco e retorna (sucesso: bool, mensagem: str) """
    if dados.get('cancelada'):
        return False, f"Atenção: A nota {dados.get('chave_acesso')} consta como Cancelada."

    chave = dados['chave_acesso']
    
    if Receipt.objects.filter(access_key=chave).exists():
        return False, f"A nota {chave} já foi cadastrada."

    data_emissao = dados.get('data_emissao')
    if isinstance(data_emissao, str):
        try:
            data_emissao = datetime.fromisoformat(data_emissao)
        except ValueError:
            data_emissao = None

    if data_emissao and not is_aware(data_emissao):
        data_emissao = make_aware(data_emissao)

    cnpj = dados.get('cnpj')
    nome_est = dados.get('estabelecimento')
    endereco_est = dados.get('endereco', '')
    
    if cnpj:
        est, _ = Establishment.objects.get_or_create(
            cnpj=cnpj, defaults={'name': nome_est, 'address': endereco_est}
        )
    else:
        est, _ = Establishment.objects.get_or_create(name=nome_est)

    nota = Receipt.objects.create(
        user=user, 
        establishment=est, 
        issue_date=data_emissao,
        total_amount=dados['total_nota'], 
        access_key=chave
    )

    for item in dados['itens']:
        codigo = item.get('codigo')
        if codigo:
            produto, _ = Product.objects.get_or_create(
                barcode=codigo, defaults={'name': item['nome']}
            )
        else:
            produto, _ = Product.objects.get_or_create(name=item['nome'])

        ReceiptItem.objects.create(
            receipt=nota, 
            product=produto, 
            quantity=item['quantidade'],
            unit_price=item['preco_unitario'], 
            total_price=item['preco_total']
        )
        
    return True, f"Nota {chave} salva com sucesso!"