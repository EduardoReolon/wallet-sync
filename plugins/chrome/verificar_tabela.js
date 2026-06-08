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
