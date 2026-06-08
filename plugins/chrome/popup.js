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
          // Agora enviamos a lista de objetos contendo { url, html }
          body: JSON.stringify({ notas: payloadNotas }) 
        });

        const resultado = await response.json();
        alert(`Sincronização concluída!\nSucessos: ${resultado.sucessos}\nErros: ${resultado.erros}`);
      } catch (err) {
        alert(`Erro de conexão com o servidor: ${err.message}`);
      }
    });
  });
});