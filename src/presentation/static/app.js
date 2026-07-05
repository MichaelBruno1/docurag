/**
 * DocuRAG Front-End Application Logic
 * Pure Vanilla JavaScript (ES6)
 */

document.addEventListener("DOMContentLoaded", () => {
    // API State and Credentials
    let API_KEY = localStorage.getItem("docurag_api_key") || "docurag_secret_api_key_v1";
    const API_URL = ""; // Relative paths since frontend is co-hosted with API

    // DOM Elements
    const apiKeyInput = document.getElementById("api-key-input");
    const saveKeyBtn = document.getElementById("save-key-btn");
    const healthDot = document.getElementById("health-dot");
    const healthText = document.getElementById("health-text");
    
    // Ingestion Elements
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const selectedFileName = document.getElementById("selected-file-name");
    const uploadBtn = document.getElementById("upload-btn");
    const exportRagBtn = document.getElementById("export-rag-btn");
    const documentsTbody = document.getElementById("documents-tbody");
    
    // Chat Elements
    const chatMessages = document.getElementById("chat-messages");
    const queryInput = document.getElementById("query-input");
    const sendQueryBtn = document.getElementById("send-query-btn");
    
    // Stats Elements
    const statActiveDocs = document.getElementById("stat-active-docs");
    const statQueuedJobs = document.getElementById("stat-queued-jobs");
    const serviceSqlite = document.getElementById("service-sqlite");
    const serviceQdrant = document.getElementById("service-qdrant");
    const serviceRedis = document.getElementById("service-redis");
    
    // Benchmark Elements
    const benchmarkLabelInput = document.getElementById("benchmark-label-input");
    const benchmarkQuestionsInput = document.getElementById("benchmark-questions-input");
    const runBenchmarkBtn = document.getElementById("run-benchmark-btn");
    const benchmarkLoader = document.getElementById("benchmark-loader");
    const benchmarkTbody = document.getElementById("benchmark-tbody");

    // Initialize API Key input field
    apiKeyInput.value = API_KEY;

    // Toast Notification helper
    function showToast(message, type = "success") {
        const toast = document.getElementById("toast");
        toast.textContent = message;
        toast.style.borderLeftColor = type === "error" ? "var(--danger)" : (type === "warning" ? "var(--warning)" : "var(--primary)");
        toast.classList.add("show");
        setTimeout(() => {
            toast.classList.remove("show");
        }, 4000);
    }

    // Save API Key handler
    saveKeyBtn.addEventListener("click", () => {
        API_KEY = apiKeyInput.value.trim();
        localStorage.setItem("docurag_api_key", API_KEY);
        showToast("Chave de API salva com sucesso!");
        checkHealth();
        fetchStats();
        fetchBenchmarkHistory();
    });

    // ----------------------------------------------------
    // SYSTEM MONITORING (HEALTH & STATS)
    // ----------------------------------------------------
    async function checkHealth() {
        try {
            const response = await fetch(`${API_URL}/health`);
            if (!response.ok) throw new Error("HTTP error " + response.status);
            
            const data = await response.json();
            
            // Set global indicators
            if (data.status === "healthy") {
                healthDot.className = "dot online";
                healthText.textContent = "Online";
            } else {
                healthDot.className = "dot offline";
                healthText.textContent = "Não saudável";
            }
            
            // Set service specific indicators
            updateServiceStatus(serviceSqlite, data.services.sqlite === "online");
            updateServiceStatus(serviceQdrant, data.services.qdrant === "online");
            updateServiceStatus(serviceRedis, data.services.redis === "online");
            
        } catch (error) {
            console.error("Erro na verificação de saúde:", error);
            healthDot.className = "dot offline";
            healthText.textContent = "Desconectado";
            updateServiceStatus(serviceSqlite, false);
            updateServiceStatus(serviceQdrant, false);
            updateServiceStatus(serviceRedis, false);
        }
    }

    function updateServiceStatus(element, isOnline) {
        if (isOnline) {
            element.className = "status-badge online";
            element.textContent = "Online";
        } else {
            element.className = "status-badge offline";
            element.textContent = "Offline";
        }
    }

    async function fetchStats() {
        try {
            const response = await fetch(`${API_URL}/stats`, {
                headers: { "X-API-Key": API_KEY }
            });
            if (!response.ok) return;
            
            const data = await response.json();
            
            // Update stats panel
            statActiveDocs.textContent = data.documentos_totais || 0;
            statQueuedJobs.textContent = data.fila_trabalhos_pendentes || 0;
            
        } catch (error) {
            console.error("Erro ao buscar estatísticas:", error);
        }
    }

    // ----------------------------------------------------
    // DOCUMENT INGESTION (FILE UPLOADING)
    // ----------------------------------------------------
    let selectedFile = null;

    // File Drag & Drop events
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFileSelection(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (fileInput.files.length > 0) {
            handleFileSelection(fileInput.files[0]);
        }
    });

    function handleFileSelection(file) {
        selectedFile = file;
        selectedFileName.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        uploadBtn.disabled = false;
    }

    // Upload Document
    uploadBtn.addEventListener("click", async () => {
        if (!selectedFile) return;
        
        uploadBtn.disabled = true;
        uploadBtn.textContent = "Enviando...";
        
        const formData = new FormData();
        formData.append("file", selectedFile);
        
        try {
            const response = await fetch(`${API_URL}/documents/ingest`, {
                method: "POST",
                headers: { "X-API-Key": API_KEY },
                body: formData
            });
            
            if (response.status === 401) {
                showToast("Erro: Chave de API inválida ou não informada.", "error");
                throw new Error("Não autorizado");
            }
            
            if (!response.ok) {
                throw new Error("Erro na resposta do servidor: " + response.status);
            }
            
            const data = await response.json();
            showToast(`Arquivo "${data.nome_arquivo}" enviado para processamento assíncrono.`);
            
            // Add document to track table
            addDocumentToTable(data.document_id, data.nome_arquivo, data.status);
            
            // Clear selection
            selectedFile = null;
            selectedFileName.textContent = "Nenhum arquivo selecionado";
            fileInput.value = "";
            
            // Poll for status update
            pollDocumentStatus(data.document_id);
            
        } catch (error) {
            console.error("Erro no envio:", error);
            showToast("Erro ao processar envio do documento.", "error");
        } finally {
            uploadBtn.textContent = "Indexar Documento";
        }
    });

    const activeIngestions = {};

    function addDocumentToTable(id, name, status) {
        // Clear empty state if present
        const emptyRow = documentsTbody.querySelector(".empty-state");
        if (emptyRow) {
            documentsTbody.innerHTML = "";
        }
        
        // Remove duplicate row if exists
        const existingRow = document.getElementById(`doc-row-${id}`);
        if (existingRow) existingRow.remove();
        
        const row = document.createElement("tr");
        row.id = `doc-row-${id}`;
        
        row.innerHTML = `
            <td title="${name}">${name}</td>
            <td><span id="doc-status-${id}" class="status-badge ${status}">${status}</span></td>
            <td style="text-align: center;">
                <button class="btn-delete-doc" onclick="deleteDocument('${id}', '${name}')" title="Excluir do RAG">🗑️</button>
            </td>
        `;
        
        documentsTbody.insertBefore(row, documentsTbody.firstChild);
    }

    // Global wrapper for inline delete button
    window.deleteDocument = async function(id, name) {
        if (!confirm(`Tem certeza de que deseja apagar permanentemente o documento "${name}" do banco vetorial e do disco?`)) return;
        
        try {
            const response = await fetch(`${API_URL}/documents/${id}`, {
                method: "DELETE",
                headers: { "X-API-Key": API_KEY }
            });
            
            if (response.ok) {
                showToast(`Documento "${name}" apagado com sucesso.`);
                const row = document.getElementById(`doc-row-${id}`);
                if (row) row.remove();
                
                // If table is empty, show empty state
                if (documentsTbody.children.length === 0) {
                    documentsTbody.innerHTML = `<tr><td colspan="3" class="empty-state">Nenhum documento processado nesta sessão.</td></tr>`;
                }
                
                fetchStats();
            } else {
                showToast(`Erro ao apagar documento (HTTP ${response.status}).`, "error");
            }
        } catch (error) {
            console.error("Erro ao deletar documento:", error);
            showToast("Erro de rede ao apagar o documento.", "error");
        }
    }

    function pollDocumentStatus(id) {
        if (activeIngestions[id]) return; // Already polling
        
        activeIngestions[id] = setInterval(async () => {
            try {
                const response = await fetch(`${API_URL}/documents/${id}`, {
                    headers: { "X-API-Key": API_KEY }
                });
                if (!response.ok) return;
                
                const data = await response.json();
                const badge = document.getElementById(`doc-status-${id}`);
                if (badge) {
                    badge.className = `status-badge ${data.status}`;
                    badge.textContent = data.status;
                }
                
                // If final state, stop polling
                if (data.status === "concluido" || data.status === "erro") {
                    clearInterval(activeIngestions[id]);
                    delete activeIngestions[id];
                    showToast(`Processamento de "${data.nome_arquivo}" finalizado com status: ${data.status}.`);
                    fetchStats();
                }
                
            } catch (error) {
                console.error("Erro ao pollar status:", error);
            }
        }, 4000);
    }

    // ----------------------------------------------------
    // CHAT RAG PLAYGROUND
    // ----------------------------------------------------
    sendQueryBtn.addEventListener("click", performQuery);
    queryInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") performQuery();
    });

    async function performQuery() {
        const query = queryInput.value.trim();
        if (!query) return;
        
        // Append user query to chat screen
        appendChatMessage("user", query);
        queryInput.value = "";
        
        // Disable actions during generation
        queryInput.disabled = true;
        sendQueryBtn.disabled = true;
        
        // Show loading message bubble
        const loadingId = appendChatMessage("assistant", "Pensando e recuperando chunks...");
        
        try {
            const start = performance.now();
            const response = await fetch(`${API_URL}/query`, {
                method: "POST",
                headers: {
                    "X-API-Key": API_KEY,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ query: query, top_k: 3 })
            });
            
            if (response.status === 401) {
                updateChatMessage(loadingId, "Erro: Não autorizado. Verifique sua X-API-Key no topo da página.");
                return;
            }
            
            if (!response.ok) {
                throw new Error("HTTP error " + response.status);
            }
            
            const data = await response.json();
            const elapsed = ((performance.now() - start) / 1000).toFixed(2);
            
            // Format answer with bold tags and formatting clean up
            let formattedResponse = data.response.replace(/\n/g, "<br>");
            
            // Build citation sources list
            let citationHtml = "";
            if (data.used_chunks && data.used_chunks.length > 0) {
                const pills = data.used_chunks.map(c => {
                    const pageStr = c.pagina ? `, Pág. ${c.pagina}` : "";
                    return `<span class="citation-card" title="Seção: ${c.secao || 'Não informada'} | Score: ${c.score ? c.score.toFixed(2) : 'N/A'}">
                        📄 ${c.nome_arquivo || 'doc'}${pageStr}
                    </span>`;
                }).join("");
                
                citationHtml = `
                    <div class="citation-container">
                        <div class="citation-header">Fontes Citadas</div>
                        <div class="citation-cards">${pills}</div>
                    </div>
                `;
            }
            
            const latencyMetaHtml = `
                <div class="latency-meta">
                    <span>⚡ RAG total: ${elapsed}s</span>
                    <span>🔍 Chunks: ${data.used_chunks ? data.used_chunks.length : 0}</span>
                </div>
            `;
            
            updateChatMessage(loadingId, `${formattedResponse}${citationHtml}${latencyMetaHtml}`);
            
        } catch (error) {
            console.error("Erro na busca RAG:", error);
            updateChatMessage(loadingId, "Erro de comunicação ao recuperar informações da base vetorial.");
        } finally {
            queryInput.disabled = false;
            sendQueryBtn.disabled = false;
            queryInput.focus();
        }
    }

    function appendChatMessage(sender, text) {
        const id = "msg-" + Math.random().toString(36).substr(2, 9);
        const bubble = document.createElement("div");
        bubble.className = `message ${sender}`;
        bubble.id = id;
        bubble.innerHTML = `
            <div class="message-content">
                ${text}
            </div>
        `;
        chatMessages.appendChild(bubble);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return id;
    }

    function updateChatMessage(id, text) {
        const bubble = document.getElementById(id);
        if (bubble) {
            const content = bubble.querySelector(".message-content");
            if (content) {
                content.innerHTML = text;
            }
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    // ----------------------------------------------------
    // BENCHMARK EXPERIMENTAL RUNNER
    // ----------------------------------------------------
    runBenchmarkBtn.addEventListener("click", async () => {
        const label = benchmarkLabelInput.value.trim() || "Padrão";
        const numQuestions = benchmarkQuestionsInput.value.trim() || "30";
        
        // Block UI inputs
        runBenchmarkBtn.disabled = true;
        benchmarkLabelInput.disabled = true;
        benchmarkQuestionsInput.disabled = true;
        
        // Update loader text dynamically
        const loaderText = benchmarkLoader.querySelector("p");
        if (loaderText) {
            loaderText.textContent = `Rodando avaliação de ${numQuestions} questões factuais/negativas no LLM. Isso pode levar de 30 a 60 segundos...`;
        }
        benchmarkLoader.style.display = "flex";
        
        showToast(`Executando teste comparativo de ${numQuestions} perguntas. Por favor, aguarde...`);
        
        try {
            const response = await fetch(`${API_URL}/benchmark/run?config_label=${encodeURIComponent(label)}&num_questions=${numQuestions}`, {
                method: "POST",
                headers: { "X-API-Key": API_KEY }
            });
            
            if (response.status === 401) {
                showToast("Erro: Não autorizado para rodar o benchmark.", "error");
                return;
            }
            
            if (!response.ok) {
                throw new Error("HTTP error " + response.status);
            }
            
            const data = await response.json();
            showToast(`Benchmark executado com sucesso para "${label}".`);
            
            // Refresh history
            fetchBenchmarkHistory();
            
        } catch (error) {
            console.error("Erro na rodada de benchmark:", error);
            showToast("Erro crítico durante a avaliação do benchmark.", "error");
        } finally {
            runBenchmarkBtn.disabled = false;
            benchmarkLabelInput.disabled = false;
            benchmarkQuestionsInput.disabled = false;
            benchmarkLoader.style.display = "none";
        }
    });

    async function fetchBenchmarkHistory() {
        try {
            const response = await fetch(`${API_URL}/benchmark/results`, {
                headers: { "X-API-Key": API_KEY }
            });
            if (!response.ok) return;
            
            const history = await response.json();
            
            // Clear current list
            benchmarkTbody.innerHTML = "";
            
            if (history.length === 0) {
                benchmarkTbody.innerHTML = `<tr><td colspan="4" class="empty-state">Nenhum resultado obtido.</td></tr>`;
                return;
            }
            
            // Render historical lines
            history.forEach(item => {
                const label = item.config_label || "Configuração";
                const hitRate = item.average_metrics.retrieval.hit_rate ? (item.average_metrics.retrieval.hit_rate * 100).toFixed(0) + "%" : "0%";
                const grounding = item.average_metrics.generation.grounding_accuracy ? (item.average_metrics.generation.grounding_accuracy * 100).toFixed(0) + "%" : "0%";
                const ignorance = item.average_metrics.generation.ignorance_admission_rate ? (item.average_metrics.generation.ignorance_admission_rate * 100).toFixed(0) + "%" : "0%";
                
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td style="font-weight:600;" title="${label}">${label}</td>
                    <td>${hitRate}</td>
                    <td>${grounding}</td>
                    <td>${ignorance}</td>
                `;
                benchmarkTbody.appendChild(row);
            });
            
        } catch (error) {
            console.error("Erro ao carregar histórico de benchmarks:", error);
        }
    }

    // ----------------------------------------------------
    // EXPORT RAG DATABASE
    // ----------------------------------------------------
    exportRagBtn.addEventListener("click", async () => {
        exportRagBtn.disabled = true;
        showToast("Criando arquivo ZIP com os dados do RAG. Por favor, aguarde...");
        try {
            const response = await fetch(`${API_URL}/documents/export`, {
                headers: { "X-API-Key": API_KEY }
            });
            if (response.status === 403) {
                showToast("Erro: Não autorizado para exportar os dados.", "error");
                return;
            }
            if (!response.ok) {
                throw new Error("HTTP error " + response.status);
            }
            
            // Download the file stream
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.style.display = "none";
            a.href = url;
            a.download = "docurag_export.zip";
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            showToast("Exportação RAG baixada com sucesso!");
        } catch (error) {
            console.error("Erro ao exportar base RAG:", error);
            showToast("Erro crítico ao tentar exportar base RAG.", "error");
        } finally {
            exportRagBtn.disabled = false;
        }
    });

    // ----------------------------------------------------
    // INITIALIZATION & TIMERS
    // ----------------------------------------------------
    checkHealth();
    fetchStats();
    fetchBenchmarkHistory();
    
    // Setup background interval polling (4 seconds)
    setInterval(checkHealth, 4000);
    setInterval(fetchStats, 4000);
});
