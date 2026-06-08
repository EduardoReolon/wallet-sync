// Procura a tabela específica do Notas Paraná pelo ID
const tabelaNotas = document.getElementById('notasId');

if (tabelaNotas) {
  // Encontrou a tabela! Salva no armazenamento que esta aba está pronta para captura
  chrome.storage.local.set({ 'pagina_valida': true }, () => {
    console.log('Wallet Sync: Tabela mapeada com sucesso nesta página.');
  });
} else {
  // Se não encontrar, limpa a flag para evitar capturas em páginas erradas
  chrome.storage.local.set({ 'pagina_valida': false });
}

console.log('fadsfasdf')
window.addEventListener("message", (event) => {
    // Verifica se a mensagem tem a mesma origem (segurança)
    if (event.source !== window) return;

    // Se o tipo da mensagem for o que definimos no Django...
    if (event.data && event.data.type === "CONFIGURAR_WALLET_SYNC") {
        
        // AQUI SIM podemos usar o chrome.storage, porque estamos no contexto da extensão!
        chrome.storage.local.set({ 'servidor_wallet-sync': event.data.url }, () => {
            console.log('✅ Wallet Sync configurado com sucesso para:', event.data.url);
            // Opcional: Você pode até dar um alert() aqui para avisar o usuário
            // alert('Extensão conectada ao sistema com sucesso!');
        });
    }
});
