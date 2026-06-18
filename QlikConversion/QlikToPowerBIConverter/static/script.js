document.addEventListener('DOMContentLoaded', () => {
// ══════════════════════════════════════════════════════════════
    // 🛠️ CUSTOM ANIMATED SELECT WRAPPER HANDLER (FIXED)
    // ══════════════════════════════════════════════════════════════
    const customSelectWrapper = document.getElementById('customSelectPlatform');
    const customTrigger = document.getElementById('customSelectTrigger');
    const nativeSelect = document.getElementById('platform_type');

    if (customSelectWrapper && customTrigger && nativeSelect) {
        const triggerText = customTrigger.querySelector('span');
        const customItems = customSelectWrapper.querySelectorAll('.custom-select-item');

        // Toggle open/closed state dropdown layout menu on click
        customTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            customSelectWrapper.classList.toggle('open');
        });

        // Option item click execution block handler
        customItems.forEach(item => {
            item.addEventListener('click', (e) => {
                const selectedValue = item.getAttribute('data-value');
                const selectedText = item.textContent;

                // Sync UI state layouts text
                triggerText.textContent = selectedText;
                
                // Clear old active styles and apply to current element target
                customItems.forEach(i => i.classList.remove('selected'));
                item.classList.add('selected');

                // Synchronize selection context seamlessly down to native select
                nativeSelect.value = selectedValue;

                // Fire native 'change' event to trigger placeholder routers immediately
                nativeSelect.dispatchEvent(new Event('change'));

                // Close layout panel gracefully
                customSelectWrapper.classList.remove('open');
            });
        });

        // Close dropdown menu if user clicks anywhere else outside the active region
        document.addEventListener('click', (e) => {
            if (!customSelectWrapper.contains(e.target)) {
                customSelectWrapper.classList.remove('open');
            }
        });
    }
    // ══════════════════════════════════════════════════════════════
    // 🔄 DYNAMIC PLACEHOLDER ROUTER FOR CONNECTION DETAILS
    // ══════════════════════════════════════════════════════════════
    const platformTypeSelect = document.getElementById('platform_type');
    const connectionDetailsInput = document.getElementById('connection_details');

    if (platformTypeSelect && connectionDetailsInput) {
        const platformPlaceholders = {
            "Microsoft SQL Server": 'e.g., Server=SHANJI\\SQLEXPRESS;Database=LoanManagement;Schema="dbo";Item="Loans"',
            "Excel Workbook (.xlsx)": 'e.g., C:\\Users\\username\\Downloads\\SampleData.xlsx;Item="Customers"',
            "Flat CSV Document (.csv)": 'e.g., C:\\Users\\username\\Documents\\DailySales.csv',
            "JSON Files (.json)": 'e.g., C:\\Users\\username\\Downloads\\SampleData.json',
            "PostgreSQL Database": 'e.g., Host=localhost;Database=loan_management;Schema="public";Item="loans"',
            "MySQL Database": 'e.g., Server=localhost;Database=loan_management;Item="loans"',
            "SharePoint Team Folder": 'e.g., https://company.sharepoint.com/sites/FinanceTeam'
        };

        // Update placeholder instantly when user flips the dropdown menu selection
        platformTypeSelect.addEventListener('change', (e) => {
            const selectedPlatform = e.target.value;
            connectionDetailsInput.placeholder = platformPlaceholders[selectedPlatform] || 'Enter connection details...';
        });
    }
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    
    const resultContainer = document.getElementById('resultContainer');
    const generatedCode = document.getElementById('generatedCode');
    const metadataContainer = document.getElementById('metadataContainer');
    const copyBtn = document.getElementById('copyBtn');

    // Toggle Generator buttons
    const btnPowerQuery = document.getElementById('btn-power-query');
    const btnDax = document.getElementById('btn-dax');
    
    // PQ vs DAX Containers
    const pqUploadContainer = document.getElementById('pqUploadContainer');
    const daxUploadContainer = document.getElementById('daxUploadContainer');
    const daxResultContainer = document.getElementById('daxResultContainer');
    const mappingContainer = document.getElementById('mappingContainer');
    
    // DAX Inputs
    const dropZoneDaxExcel = document.getElementById('dropZoneDaxExcel');
    const daxExcelInput = document.getElementById('daxExcelInput');
    const browseDaxExcelBtn = document.getElementById('browseDaxExcelBtn');
    
    const dropZoneDaxMetadata = document.getElementById('dropZoneDaxMetadata');
    const daxMetadataInput = document.getElementById('daxMetadataInput');
    const browseDaxMetadataBtn = document.getElementById('browseDaxMetadataBtn');
    
    const daxPreviewSection = document.getElementById('daxPreviewSection');
    const daxPreviewTableContainer = document.getElementById('daxPreviewTableContainer');
    const btnGenerateDax = document.getElementById('btnGenerateDax');

    btnPowerQuery.addEventListener('click', () => {
        btnPowerQuery.classList.add('active');
        btnPowerQuery.querySelector('span').className = 'dot';
        btnDax.classList.remove('active');
        btnDax.querySelector('span').className = 'dot-inactive';
        
        pqUploadContainer.classList.remove('hidden');
        if (resultContainer.dataset.active === "true") {
            resultContainer.classList.remove('hidden');
        }
        if (mappingContainer && resultContainer.dataset.active === "true") {
            mappingContainer.classList.remove('hidden');
        }
        daxUploadContainer.classList.add('hidden');
        daxResultContainer.classList.add('hidden');
    });

    btnDax.addEventListener('click', () => {
        btnDax.classList.add('active');
        btnDax.querySelector('span').className = 'dot';
        btnPowerQuery.classList.remove('active');
        btnPowerQuery.querySelector('span').className = 'dot-inactive';
        
        daxUploadContainer.classList.remove('hidden');
        if (daxResultContainer.dataset.active === "true") {
            daxResultContainer.classList.remove('hidden');
        }
        pqUploadContainer.classList.add('hidden');
        resultContainer.classList.add('hidden');
        if (mappingContainer) {
            mappingContainer.classList.add('hidden');
        }
    });

    // Trigger file input on button click
    browseBtn.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle drag events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('dragover');
        });
    });

    // Handle file drop
    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    });

    // Handle file input selection
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length === 0) return;
        const file = files[0];
        
        // Check extension
        const ext = file.name.split('.').pop().toLowerCase();
        if (ext !== 'qvs' && ext !== 'txt') {
            alert('Please upload a .qvs or .txt file');
            return;
        }

        uploadFile(file);
    }

    let currentRawText = "";

    async function uploadFile(file) {
        dropZone.innerHTML = `<h3>Uploading and analyzing ${file.name}...</h3><p>Please wait, AI engine is processing...</p>`;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                currentRawText = data.raw_text;
                
                // Show mapping container
                document.getElementById('mappingContainer').classList.remove('hidden');
                document.getElementById('sourceCode').textContent = currentRawText;
                
                // Build mapping inputs
                // Code view visibility trigger block
                document.getElementById('mappingContainer').classList.remove('hidden');
                document.getElementById('sourceCode').textContent = currentRawText;

                resetDropZone();
                document.getElementById('dropZone').innerHTML = `<div class="upload-icon">✓</div><h3>File uploaded successfully</h3><p>Scroll down to map files and generate code.</p>`;
                
            } else {
                alert('Error processing file: ' + data.error);
                resetDropZone();
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred during upload.');
            resetDropZone();
        }
    }

    document.getElementById('btnGenerate').addEventListener('click', async () => {
        const btn = document.getElementById('btnGenerate');
        const originalText = btn.textContent;
        btn.textContent = 'Generating...';
        btn.disabled = true;

        const file_mappings = {};
        const inputs = document.querySelectorAll('.mapping-input');
        inputs.forEach(inp => {
            if (inp.value.trim() !== '') {
                file_mappings[inp.getAttribute('data-source')] = inp.value.trim();
            }
        });

        // Check manual
        const manualName = document.getElementById('manualSourceName');
        const manualPath = document.getElementById('manualSourcePath');
        if (manualName && manualPath && manualName.value.trim() !== '' && manualPath.value.trim() !== '') {
            file_mappings[manualName.value.trim()] = manualPath.value.trim();
        }

        try {
            // NEW: Fetch input values from the Data Platform UI components
            const platformType = document.getElementById('platform_type').value;
            const connectionDetails = document.getElementById('connection_details').value;

            // Safe fallback: append parameters directly to file_mappings dictionary too
            file_mappings["platform_type"] = platformType;
            file_mappings["connection_details"] = connectionDetails;

            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    raw_text: currentRawText,
                    file_mappings: file_mappings,
                    platform_type: platformType,         // Sent to match Pydantic Schema model
                    connection_details: connectionDetails // Sent to match Pydantic Schema model
                })
            });

            const data = await response.json();

            if (data.success) {
                resultContainer.classList.remove('hidden');
                resultContainer.dataset.active = "true";
                
                // 1. Detected Tables
                const dt = document.getElementById('detectedTables');
                if (data.table_blocks && data.table_blocks.length > 0) {
                    let html = '<div style="display: flex; gap: 1rem; flex-wrap: wrap;">';
                    data.table_blocks.forEach((block, idx) => {
                        const tname = (block.table && block.table.name) ? block.table.name : `Table ${idx + 1}`;
                        const ncols = block.columns ? block.columns.length : 0;
                        const nsrc = block.sources ? block.sources.length : 0;
                        const is_res = block.is_resident || false;
                        const kind = is_res ? "RESIDENT" : "FILE";
                        
                        html += `
                            <div style="background-color: var(--bg-card, #1e293b); border: 1px solid var(--border-color, #334155); border-radius: 8px; padding: 1rem; min-width: 200px; flex: 1;">
                                <h4 style="margin: 0 0 0.5rem 0; color: #fff; font-size: 0.95rem;">${tname}</h4>
                                <p style="margin: 0; font-size: 0.8rem; color: var(--text-secondary, #94a3b8);">
                                    ${ncols} columns &middot; ${nsrc} source &middot; ${kind}
                                </p>
                            </div>
                        `;
                    });
                    html += '</div>';
                    dt.innerHTML = html;
                } else {
                    dt.textContent = "No table declarations were found.";
                }

                // 2. Detected ETL Ops
                const ops = document.getElementById('detectedOps');
                if (data.operations && data.operations.length > 0) {
                    ops.innerHTML = `<ul style="margin:0; padding-left:1rem;">${data.operations.map(o => `<li>${o}</li>`).join('')}</ul>`;
                } else {
                    ops.textContent = "None";
                }

                // 3. Source File Mapping
                const sfm = document.getElementById('sourceFileMappingResult');
                if (Object.keys(file_mappings).length > 0) {
                    let html = '<div style="background-color: var(--bg-card, #1e293b); border: 1px solid var(--border-color, #334155); border-radius: 8px; overflow: hidden;">';
                    html += '<table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.85rem;">';
                    html += '<thead><tr style="background-color: rgba(255,255,255,0.05); border-bottom: 1px solid var(--border-color, #334155);"><th style="padding: 0.75rem; color: #fff;">Qlik Source</th><th style="padding: 0.75rem; color: #fff;">Power BI Path</th></tr></thead><tbody>';
                    for (const [qSrc, pbiPath] of Object.entries(file_mappings)) {
                        html += `<tr style="border-bottom: 1px solid var(--border-color, #334155);"><td style="padding: 0.75rem; color: var(--text-secondary, #94a3b8);">${qSrc}</td><td style="padding: 0.75rem; color: var(--text-secondary, #94a3b8); font-family: monospace;">${pbiPath}</td></tr>`;
                    }
                    html += '</tbody></table></div>';
                    sfm.innerHTML = html;
                } else {
                    sfm.textContent = "No mappings provided.";
                }

                // 4. Parsed Metadata
                document.getElementById('parsedMetadata').textContent = JSON.stringify(data.metadata, null, 2);

                // 5. Generated Code & Tabs
                const tabsContainer = document.getElementById('tableTabs');
                const generatedCodeEl = document.getElementById('generatedCode');
                const btnDownloadSingle = document.getElementById('btnDownloadSingle');
                const btnDownloadAll = document.getElementById('btnDownloadAll');
                const btnDownloadJson = document.getElementById('btnDownloadJson');
                
                tabsContainer.innerHTML = '';
                let currentTableData = null;
                
                if (data.per_table && data.per_table.length > 0) {
                    data.per_table.forEach((tb, index) => {
                        const btn = document.createElement('button');
                        btn.textContent = tb.table;
                        btn.style.padding = '0.5rem 1rem';
                        btn.style.border = 'none';
                        btn.style.borderRadius = '4px';
                        btn.style.cursor = 'pointer';
                        btn.style.fontSize = '0.85rem';
                        
                        if (index === 0) {
                            btn.style.background = '#3b82f6';
                            btn.style.color = 'white';
                            currentTableData = tb;
                            generatedCodeEl.textContent = tb.m_code;
                            btnDownloadSingle.textContent = `⬇ Download ${tb.table}.pq`;
                        } else {
                            btn.style.background = 'transparent';
                            btn.style.color = '#cbd5e1';
                        }
                        
                        btn.addEventListener('click', () => {
                            Array.from(tabsContainer.children).forEach(c => {
                                c.style.background = 'transparent';
                                c.style.color = '#cbd5e1';
                            });
                            btn.style.background = '#3b82f6';
                            btn.style.color = 'white';
                            
                            currentTableData = tb;
                            generatedCodeEl.textContent = tb.m_code;
                            btnDownloadSingle.textContent = `⬇ Download ${tb.table}.pq`;
                        });
                        
                        tabsContainer.appendChild(btn);
                    });
                } else {
                    generatedCodeEl.textContent = data.generated_m;
                }

                btnDownloadSingle.onclick = () => {
                    if (currentTableData) downloadFile(currentTableData.m_code, `${currentTableData.table}.pq`, 'text/plain');
                };
                btnDownloadAll.onclick = () => {
                    downloadFile(data.generated_m, 'Combined_Tables.pq', 'text/plain');
                };
                btnDownloadJson.onclick = () => {
                    downloadFile(JSON.stringify(data.metadata, null, 2), 'Schema_Metadata.json', 'application/json');
                };

                // 6. Warnings
                const warnBox = document.getElementById('warningsBox');
                if (data.warnings && data.warnings.length > 0) {
                    warnBox.style.background = '#450a0a';
                    warnBox.style.color = '#f87171';
                    warnBox.style.borderColor = '#7f1d1d';
                    warnBox.innerHTML = `<ul style="margin:0; padding-left:1rem;">${data.warnings.map(w => `<li>${w}</li>`).join('')}</ul>`;
                } else {
                    warnBox.style.background = '#064e3b';
                    warnBox.style.color = '#10b981';
                    warnBox.style.borderColor = '#064e3b';
                    warnBox.textContent = "No unsupported features were flagged.";
                }
                
                // 7. Logs
                const now = new Date();
                const timeStr = now.toISOString().replace('T', ' ').substring(0, 19);
                const logs = `${timeStr} [INFO] Qlik script uploaded\n${timeStr} [INFO] Power Query M generation started\n${timeStr} [INFO] Generation complete. Extracted ${data.per_table ? data.per_table.length : 0} tables.`;
                document.getElementById('migrationLogs').textContent = logs;
                
                // Scroll to results
                resultContainer.scrollIntoView({ behavior: 'smooth' });
            } else {
                alert('Error generating code: ' + data.error);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred during generation.');
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    });

    function resetDropZone() {
        dropZone.innerHTML = `
            <div class="upload-icon">📄</div>
            <h3>Drag and drop your file here</h3>
            <p>Accepts <span class="tag">.qvs</span>, <span class="tag">.txt</span> • Max 20 MB per file</p>
            <button class="btn btn-outline" id="browseBtnRe">Browse files</button>
        `;
        document.getElementById('browseBtnRe').addEventListener('click', () => {
            fileInput.click();
        });
    }

    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(generatedCode.textContent).then(() => {
                copyBtn.textContent = 'Copied!';
                setTimeout(() => { copyBtn.textContent = 'Copy Code'; }, 2000);
            });
        });
    }

    function downloadFile(content, filename, type) {
        const blob = new Blob([content], { type: type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    // ══════════════════════════════════════════════════════════════
    // 📊 DAX GENERATION EVENT HANDLERS & FETCH LOGIC
    // ══════════════════════════════════════════════════════════════
    let daxExcelFile = null;
    let daxMetadataFile = null;

    browseDaxExcelBtn.addEventListener('click', () => daxExcelInput.click());
    browseDaxMetadataBtn.addEventListener('click', () => daxMetadataInput.click());

    daxExcelInput.addEventListener('change', function() {
        handleDaxExcel(this.files);
    });
    daxMetadataInput.addEventListener('change', function() {
        handleDaxMetadata(this.files);
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZoneDaxExcel.addEventListener(eventName, preventDefaults, false);
        dropZoneDaxMetadata.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZoneDaxExcel.addEventListener(eventName, () => dropZoneDaxExcel.classList.add('dragover'));
        dropZoneDaxMetadata.addEventListener(eventName, () => dropZoneDaxMetadata.classList.add('dragover'));
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZoneDaxExcel.addEventListener(eventName, () => dropZoneDaxExcel.classList.remove('dragover'));
        dropZoneDaxMetadata.addEventListener(eventName, () => dropZoneDaxMetadata.classList.remove('dragover'));
    });

    dropZoneDaxExcel.addEventListener('drop', (e) => {
        handleDaxExcel(e.dataTransfer.files);
    });
    dropZoneDaxMetadata.addEventListener('drop', (e) => {
        handleDaxMetadata(e.dataTransfer.files);
    });

    async function handleDaxExcel(files) {
        if (files.length === 0) return;
        const file = files[0];
        const ext = file.name.split('.').pop().toLowerCase();
        if (ext !== 'xlsx' && ext !== 'csv') {
            alert('Please upload a .xlsx or .csv file');
            return;
        }
        daxExcelFile = file;
        dropZoneDaxExcel.innerHTML = `<div class="upload-icon">✓</div><h3>${file.name}</h3><p>Mapping sheet loaded successfully.</p>`;
        
        daxPreviewSection.classList.remove('hidden');
        daxPreviewTableContainer.innerHTML = '<p style="padding:1rem; color:var(--text-secondary);">Loading preview...</p>';
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/dax/preview', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.success) {
                renderPreviewTable(data.columns, data.rows);
            } else {
                daxPreviewTableContainer.innerHTML = `<p style="padding:1rem; color:red;">Failed to load preview: ${data.error}</p>`;
            }
        } catch (error) {
            daxPreviewTableContainer.innerHTML = `<p style="padding:1rem; color:red;">Failed to load preview.</p>`;
        }
    }

    function renderPreviewTable(columns, rows) {
        let html = '<table style="width:100%; border-collapse:collapse; font-size:0.85rem; text-align:left;">';
        html += '<thead style="background:rgba(255,255,255,0.05); border-bottom:1px solid var(--border-color);">';
        html += '<tr>';
        columns.forEach(col => {
            html += `<th style="padding:0.5rem 0.75rem; color:#fff; border-right:1px solid var(--border-color);">${col}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        rows.forEach(row => {
            html += '<tr style="border-bottom:1px solid var(--border-color);">';
            row.forEach(cell => {
                html += `<td style="padding:0.5rem 0.75rem; color:var(--text-secondary); border-right:1px solid var(--border-color); white-space:nowrap; max-width:200px; overflow:hidden; text-overflow:ellipsis;">${cell}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        daxPreviewTableContainer.innerHTML = html;
    }

    function handleDaxMetadata(files) {
        if (files.length === 0) return;
        const file = files[0];
        const ext = file.name.split('.').pop().toLowerCase();
        if (ext !== 'json') {
            alert('Please upload a .json file');
            return;
        }
        daxMetadataFile = file;
        dropZoneDaxMetadata.innerHTML = `<div class="upload-icon">✓</div><h3>${file.name}</h3><p>Schema metadata context active.</p>`;
    }

    btnGenerateDax.addEventListener('click', async () => {
        if (!daxExcelFile) {
            alert("Please upload a Set Analysis mapping sheet first.");
            return;
        }
        
        const originalText = btnGenerateDax.textContent;
        btnGenerateDax.textContent = 'Generating DAX...';
        btnGenerateDax.disabled = true;
        
        const formData = new FormData();
        formData.append('file', daxExcelFile);
        if (daxMetadataFile) {
            formData.append('schema_context', daxMetadataFile);
        }
        
        try {
            const response = await fetch('/api/dax/generate', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (data.success) {
                daxResultContainer.classList.remove('hidden');
                daxResultContainer.dataset.active = "true";
                
                document.getElementById('kpiDaxProcessed').textContent = data.total_rows;
                document.getElementById('kpiDaxPassed').textContent = data.total_rows - data.conversion_errors_count;
                document.getElementById('kpiDaxAlerts').textContent = data.validation_logs.length;
                
                renderDaxReportTable(data.results);
                
                const valErrorsSect = document.getElementById('daxValidationErrorsSection');
                const valErrors = document.getElementById('daxValidationErrors');
                if (data.validation_logs && data.validation_logs.length > 0) {
                    valErrorsSect.classList.remove('hidden');
                    
                    let html = '<table style="width:100%; border-collapse:collapse; text-align:left; font-size:0.85rem;">';
                    html += '<thead style="background:rgba(255,255,255,0.05); border-bottom:1px solid var(--border-color);">';
                    html += '<tr><th style="padding:0.5rem; color:#fff;">Row</th><th style="padding:0.5rem; color:#fff;">Measure Name</th><th style="padding:0.5rem; color:#fff;">Errors</th><th style="padding:0.5rem; color:#fff;">Warnings</th></tr></thead><tbody>';
                    data.validation_logs.forEach(log => {
                        html += `<tr style="border-bottom:1px solid var(--border-color);">`;
                        html += `<td style="padding:0.5rem; color:var(--text-secondary);">${log.Row}</td>`;
                        html += `<td style="padding:0.5rem; font-weight:600; color:#fff;">${log['Measure Name']}</td>`;
                        html += `<td style="padding:0.5rem; color:var(--danger);">${log['Validation Errors']}</td>`;
                        html += `<td style="padding:0.5rem; color:orange;">${log['Validation Warnings']}</td>`;
                        html += '</tr>';
                    });
                    html += '</tbody></table>';
                    valErrors.innerHTML = html;
                } else {
                    valErrorsSect.classList.add('hidden');
                }
                
                const btnDownloadDaxPackage = document.getElementById('btnDownloadDaxPackage');
                btnDownloadDaxPackage.onclick = () => {
                    const blob = b64toBlob(data.excel_package, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
                    downloadBlob(blob, 'DAX_Migration_Comprehensive_Package.xlsx');
                };
                
                const now = new Date();
                const timeStr = now.toISOString().replace('T', ' ').substring(0, 19);
                const logs = `${timeStr} [INFO] Set Analysis mapping sheet uploaded\n${timeStr} [INFO] Context-Aware DAX generation started\n${timeStr} [INFO] Conversion complete. Generated ${data.total_rows} measures.`;
                document.getElementById('daxMigrationLogs').textContent = logs;
                
                daxResultContainer.scrollIntoView({ behavior: 'smooth' });
                
            } else {
                alert('Error generating DAX: ' + data.error);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred during DAX generation.');
        } finally {
            btnGenerateDax.textContent = originalText;
            btnGenerateDax.disabled = false;
        }
    });

    function renderDaxReportTable(results) {
        const daxReportTableContainer = document.getElementById('daxReportTableContainer');
        
        let html = '<table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.85rem;">';
        html += '<thead><tr style="background-color: rgba(255,255,255,0.05); border-bottom: 1px solid var(--border-color);">';
        html += '<th style="padding: 0.75rem; color: #fff;">Status</th>';
        html += '<th style="padding: 0.75rem; color: #fff;">Measure Name</th>';
        html += '<th style="padding: 0.75rem; color: #fff;">Target Table</th>';
        html += '<th style="padding: 0.75rem; color: #fff;">Qlik Expression</th>';
        html += '<th style="padding: 0.75rem; color: #fff;">DAX Output</th>';
        html += '<th style="padding: 0.75rem; color: #fff;">Pattern</th>';
        html += '<th style="padding: 0.75rem; color: #fff;">Exec (ms)</th>';
        html += '</tr></thead><tbody>';
        
        results.forEach(row => {
            const statusPill = row.Status === "PASSED" 
                ? '<span style="background-color:#E8F5E9; color:#2E7D32; padding:4px 12px; border: 1px solid #C8E6C9; border-radius:50px; font-size:11px; font-weight:700;">✔ PASSED</span>'
                : '<span style="background-color:#FFEBEE; color:#C62828; padding:4px 12px; border: 1px solid #FFCDD2; border-radius:50px; font-size:11px; font-weight:700;">✘ FAILED</span>';
                
            html += `<tr style="border-bottom: 1px solid var(--border-color);">`;
            html += `<td style="padding: 0.75rem;">${statusPill}</td>`;
            html += `<td style="padding: 0.75rem; font-weight:600; color:#fff;">${row['Measure Name']}</td>`;
            html += `<td style="padding: 0.75rem; color:var(--text-secondary);">${row['Target Table']}</td>`;
            html += `<td style="padding: 0.75rem; color:var(--text-secondary); max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${row['Qlik Expression'].replace(/"/g, '&quot;')}">${row['Qlik Expression']}</td>`;
            html += `<td style="padding: 0.75rem; font-family:monospace; background:rgba(0,0,0,0.15); max-width:300px; overflow-x:auto; white-space:pre-wrap; color:#3b82f6;">${row['DAX Output']}</td>`;
            html += `<td style="padding: 0.75rem; color:var(--text-secondary);">${row['Pattern Framework']}</td>`;
            html += `<td style="padding: 0.75rem; color:var(--text-secondary);">${row['Execution (ms)']}</td>`;
            html += '</tr>';
        });
        
        html += '</tbody></table>';
        daxReportTableContainer.innerHTML = html;
    }

    function b64toBlob(b64Data, contentType='', sliceSize=512) {
        const byteCharacters = atob(b64Data);
        const byteArrays = [];
        for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
            const slice = byteCharacters.slice(offset, offset + sliceSize);
            const byteNumbers = new Array(slice.length);
            for (let i = 0; i < slice.length; i++) {
                byteNumbers[i] = slice.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            byteArrays.push(byteArray);
        }
        return new Blob(byteArrays, {type: contentType});
    }

    function downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }
});
