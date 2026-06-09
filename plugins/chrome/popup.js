function mostrarLogNaAba(tabId, mensagem, tipo = 'info') {
  chrome.scripting.executeScript({
    target: { tabId: tabId },
    args: [mensagem, tipo], // Passa as variáveis para dentro da página
    func: (msg, tp) => {
      let container = document.getElementById('carteira-log-flutuante');

      if (!container) {
        container = document.createElement('div');
        container.id = 'carteira-log-flutuante';
        container.style.cssText = `
          position: fixed;
          bottom: 20px;
          right: 20px;
          width: 350px;
          max-height: 300px;
          background-color: rgba(15, 23, 42, 0.95);
          color: #f8fafc;
          font-family: monospace;
          font-size: 13px;
          padding: 15px;
          border-radius: 8px;
          border: 1px solid #334155;
          z-index: 2147483647;
          overflow-y: auto;
          box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
        `;
        document.body.appendChild(container);
      }

      const linha = document.createElement('div');
      linha.style.marginBottom = '6px';
      linha.style.borderBottom = '1px dashed #334155';
      linha.style.paddingBottom = '4px';

      if (tp === 'erro') {
        linha.style.color = '#ef4444'; // Vermelho
      } else if (tp === 'sucesso') {
        linha.style.color = '#22c55e'; // Verde
      } else {
        linha.style.color = '#eab308'; // Amarelo
      }

      linha.innerText = `[${new Date().toLocaleTimeString()}] ${msg}`;
      container.appendChild(linha);
      container.scrollTop = container.scrollHeight;
    }
  });
}

document.getElementById('capturar').addEventListener('click', async () => {
  chrome.storage.local.get(['servidor_wallet-sync', 'pagina_valida'], async (result) => {
    const servidor = result['servidor_wallet-sync'];
    const paginaValida = result['pagina_valida'];

    if (!servidor) {
      alert('Erro: Abra a página do seu sistema Wallet primeiro para sincronizar o plugin.');
      return;
    }

    if (!paginaValida) {
      alert('Erro: Esta página não possui a tabela de notas fiscais (#notasId).');
      return;
    }

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    // Altera o texto do botão para dar um feedback visual (opcional)
    const btn = document.getElementById('capturar');
    const textoOriginal = btn.innerText;
    btn.innerText = 'Baixando HTML das notas...';

    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      // Transformamos a função em async para permitir o fetch
      func: async () => {
        const links = document.querySelectorAll('#notasId td a:not([id="btnRejeitar"])');
        const notasHTML = [];

        // Loop para acessar cada URL e baixar o HTML usando a sessão do navegador
        for (const link of links) {
          try {
            const response = await fetch(link.href);
            const htmlText = await response.text();
            
            notasHTML.push({
              url: link.href,
              html: htmlText
            });
          } catch (err) {
            console.error(`Falha ao baixar a nota ${link.href}`, err);
          }
        }
        return notasHTML;
      }
    }, async (results) => {
      btn.innerText = textoOriginal; // Restaura o botão

      if (!results || !results[0] || !results[0].result) return;
      
      const payloadNotas = results[0].result;

      if (payloadNotas.length === 0) {
        alert('Nenhuma nota conseguiu ser processada.');
        return;
      }

      // 4. Envia o lote (URLs + HTML) para a API do Django
      const urlFinalApi = `${servidor}/ler-notas-lote/`;

      try {
        const response = await fetch(urlFinalApi, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include', 
          body: JSON.stringify({ notas: payloadNotas }) 
        });

        const resultado = await response.json();

        if (resultado.sucesso) {
          let mensagemFinal = `Sincronização concluída!\nSucessos: ${resultado.sucessos} | Erros: ${resultado.erros}`;
          
          if (resultado.erros > 0 && resultado.detalhes_erros && resultado.detalhes_erros.length > 0) {
            const listaErros = resultado.detalhes_erros.map(e => `- ${e}`).join('\n');
            mensagemFinal += `\n\nDetalhes:\n${listaErros}`;
            
            // Passando o tab.id aqui!
            mostrarLogNaAba(tab.id, mensagemFinal, 'info'); 
          } else {
            mostrarLogNaAba(tab.id, mensagemFinal, 'sucesso');
          }

        } else {
          mostrarLogNaAba(tab.id, `Erro no servidor: ${resultado.mensagem}`, 'erro');
        }

      } catch (err) {
        mostrarLogNaAba(tab.id, `Erro de conexão: ${err.message}`, 'erro');
      }
    });
  });
});