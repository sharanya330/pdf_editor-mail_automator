document.addEventListener('DOMContentLoaded', () => {
    // Top Tabs
    const tabEnginePdf = document.getElementById('tabEnginePdf');
    const tabEngineJpeg = document.getElementById('tabEngineJpeg');
    const pdfSubNav = document.getElementById('pdfSubNav');
    const jpegSubNav = document.getElementById('jpegSubNav');

    // Sub-Tabs for PDF Editor
    const tabSingle = document.getElementById('tabSingle');
    const tabBulk = document.getElementById('tabBulk');
    const modeSingleSection = document.getElementById('modeSingleSection');
    const modeBulkSection = document.getElementById('modeBulkSection');

    // Sub-Tabs for JPEG Editor
    const tabJpegSingle = document.getElementById('tabJpegSingle');
    const tabJpegBulk = document.getElementById('tabJpegBulk');
    const modeJpegSingleSection = document.getElementById('modeJpegSingleSection');
    const modeJpegBulkSection = document.getElementById('modeJpegBulkSection');

    // Single PDF elements
    const dropZoneSingle = document.getElementById('dropZoneSingle');
    const pdfFileInput = document.getElementById('pdfFileInput');
    const fileInfo = document.getElementById('fileInfo');
    const analysisSection = document.getElementById('analysisSection');
    const modeBadge = document.getElementById('modeBadge');
    const pagesCount = document.getElementById('pagesCount');
    const imagesCount = document.getElementById('imagesCount');
    const vectorsCount = document.getElementById('vectorsCount');
    const fieldInputsContainer = document.getElementById('fieldInputsContainer');
    const addFieldBtn = document.getElementById('addFieldBtn');
    const executeEditBtn = document.getElementById('executeEditBtn');
    const nlInstruction = document.getElementById('nlInstruction');
    const downloadBtn = document.getElementById('downloadBtn');

    // Bulk PDF elements
    const bulkPdfInput = document.getElementById('bulkPdfInput');
    const bulkPdfInfo = document.getElementById('bulkPdfInfo');
    const bulkDataInput = document.getElementById('bulkDataInput');
    const bulkDataInfo = document.getElementById('bulkDataInfo');
    const bulkMappingContainer = document.getElementById('bulkMappingContainer');
    const addBulkMapBtn = document.getElementById('addBulkMapBtn');
    const executeBulkBtn = document.getElementById('executeBulkBtn');
    const bulkResultsBox = document.getElementById('bulkResultsBox');
    const bulkSummaryText = document.getElementById('bulkSummaryText');
    const downloadZipBtn = document.getElementById('downloadZipBtn');

    // Email Dispatch elements (Bulk PDF)
    const sendEmailToggle = document.getElementById('sendEmailToggle');
    const emailConfigBox = document.getElementById('emailConfigBox');
    const emailColSelect = document.getElementById('emailColSelect');
    const emailSubjectInput = document.getElementById('emailSubjectInput');
    const emailBodyInput = document.getElementById('emailBodyInput');

    // Single Email Dispatch elements (Single PDF)
    const singleSendEmailToggle = document.getElementById('singleSendEmailToggle');
    const singleEmailConfigBox = document.getElementById('singleEmailConfigBox');
    const singleEmailRecipient = document.getElementById('singleEmailRecipient');
    const singleEmailSubject = document.getElementById('singleEmailSubject');
    const singleEmailBody = document.getElementById('singleEmailBody');

    // Shared UI
    const statusAlert = document.getElementById('statusAlert');
    const statusText = document.getElementById('statusText');
    const validationResults = document.getElementById('validationResults');
    const emptyState = document.getElementById('emptyState');

    let currentFile = null;
    let bulkPdfFile = null;
    let bulkDataFile = null;
    let availableColumns = [];
    let detectedPdfFields = [];

    // Email toggle handlers
    if (sendEmailToggle && emailConfigBox) {
        sendEmailToggle.addEventListener('change', () => {
            emailConfigBox.style.display = sendEmailToggle.checked ? 'block' : 'none';
        });
    }

    if (singleSendEmailToggle && singleEmailConfigBox) {
        singleSendEmailToggle.addEventListener('change', () => {
            singleEmailConfigBox.style.display = singleSendEmailToggle.checked ? 'block' : 'none';
        });
    }

    // Auto-fetch SMTP configuration from .env / server
    async function loadSmtpConfig() {
        try {
            const resp = await fetch('/pdf/smtp-info');
            if (resp.ok) {
                const info = await resp.json();
                const envBadge = document.getElementById('envConfigBadge');
                const senderInput = document.getElementById('smtpSenderEmail');
                const hostInput = document.getElementById('smtpHost');
                const portInput = document.getElementById('smtpPort');

                if (info.sender_email && senderInput && !senderInput.value) {
                    senderInput.value = info.sender_email;
                }
                if (info.host && hostInput) {
                    hostInput.value = info.host;
                }
                if (info.port && portInput) {
                    portInput.value = info.port;
                }
                if (info.has_credentials && envBadge) {
                    envBadge.style.display = 'inline-block';
                    envBadge.style.background = '#065f46';
                    envBadge.style.color = '#34d399';
                    envBadge.textContent = `✓ .env configured (${info.sender_email})`;
                }
            }
        } catch (e) {
            console.debug("Failed to load SMTP info", e);
        }
    }
    loadSmtpConfig();

    // Auto-suggest SMTP Host & Port when user types Sender Email
    const smtpSenderEmailInput = document.getElementById('smtpSenderEmail');
    if (smtpSenderEmailInput) {
        smtpSenderEmailInput.addEventListener('blur', () => {
            const val = smtpSenderEmailInput.value.trim().toLowerCase();
            const hostInput = document.getElementById('smtpHost');
            const portInput = document.getElementById('smtpPort');
            if (!hostInput || !portInput) return;

            if (val.endsWith('@gmail.com') && (!hostInput.value || hostInput.value === 'smtp.hostinger.com')) {
                hostInput.value = 'smtp.gmail.com';
                portInput.value = '587';
            } else if ((val.endsWith('@outlook.com') || val.endsWith('@hotmail.com') || val.endsWith('@live.com')) && (!hostInput.value || hostInput.value === 'smtp.hostinger.com')) {
                hostInput.value = 'smtp-mail.outlook.com';
                portInput.value = '587';
            } else if (val.endsWith('@yahoo.com') && (!hostInput.value || hostInput.value === 'smtp.hostinger.com')) {
                hostInput.value = 'smtp.mail.yahoo.com';
                portInput.value = '465';
            }
        });
    }

    // Navigation and Tab Switching Logic
    function showTabMode(engine, subMode, updateHistory = false) {
        if (engine === 'pdf') {
            if (tabEnginePdf) tabEnginePdf.classList.add('active');
            if (tabEngineJpeg) tabEngineJpeg.classList.remove('active');
            if (pdfSubNav) pdfSubNav.style.display = 'flex';
            if (jpegSubNav) jpegSubNav.style.display = 'none';

            if (subMode === 'single') {
                if (tabSingle) tabSingle.classList.add('active');
                if (tabBulk) tabBulk.classList.remove('active');
                if (modeSingleSection) modeSingleSection.style.display = 'block';
                if (modeBulkSection) modeBulkSection.style.display = 'none';
            } else {
                if (tabBulk) tabBulk.classList.add('active');
                if (tabSingle) tabSingle.classList.remove('active');
                if (modeBulkSection) modeBulkSection.style.display = 'block';
                if (modeSingleSection) modeSingleSection.style.display = 'none';
            }
            if (modeJpegSingleSection) modeJpegSingleSection.style.display = 'none';
            if (modeJpegBulkSection) modeJpegBulkSection.style.display = 'none';

            if (updateHistory) {
                history.pushState({ engine: 'pdf', subMode }, '', '/');
            }

        } else if (engine === 'jpeg') {
            if (tabEngineJpeg) tabEngineJpeg.classList.add('active');
            if (tabEnginePdf) tabEnginePdf.classList.remove('active');
            if (jpegSubNav) jpegSubNav.style.display = 'flex';
            if (pdfSubNav) pdfSubNav.style.display = 'none';

            if (subMode === 'single') {
                if (tabJpegSingle) tabJpegSingle.classList.add('active');
                if (tabJpegBulk) tabJpegBulk.classList.remove('active');
                if (modeJpegSingleSection) modeJpegSingleSection.style.display = 'block';
                if (modeJpegBulkSection) modeJpegBulkSection.style.display = 'none';
            } else {
                if (tabJpegBulk) tabJpegBulk.classList.add('active');
                if (tabJpegSingle) tabJpegSingle.classList.remove('active');
                if (modeJpegBulkSection) modeJpegBulkSection.style.display = 'block';
                if (modeJpegSingleSection) modeJpegSingleSection.style.display = 'none';
            }
            if (modeSingleSection) modeSingleSection.style.display = 'none';
            if (modeBulkSection) modeBulkSection.style.display = 'none';

            if (updateHistory) {
                history.pushState({ engine: 'jpeg', subMode }, '', '/jpeg');
            }
        }
        resetOutputDisplays();
    }

    if (tabEnginePdf) tabEnginePdf.addEventListener('click', (e) => { e.preventDefault(); showTabMode('pdf', 'single', true); });
    if (tabEngineJpeg) tabEngineJpeg.addEventListener('click', (e) => { e.preventDefault(); showTabMode('jpeg', 'single', true); });

    if (tabSingle) tabSingle.addEventListener('click', (e) => { e.preventDefault(); showTabMode('pdf', 'single', false); });
    if (tabBulk) tabBulk.addEventListener('click', (e) => { e.preventDefault(); showTabMode('pdf', 'bulk', false); });
    if (tabJpegSingle) tabJpegSingle.addEventListener('click', (e) => { e.preventDefault(); showTabMode('jpeg', 'single', false); });
    if (tabJpegBulk) tabJpegBulk.addEventListener('click', (e) => { e.preventDefault(); showTabMode('jpeg', 'bulk', false); });

    window.addEventListener('popstate', () => {
        if (window.location.pathname.startsWith('/jpeg')) {
            showTabMode('jpeg', 'single', false);
        } else {
            showTabMode('pdf', 'single', false);
        }
    });

    // Initial page load mode check based on URL path
    if (window.location.pathname.startsWith('/jpeg')) {
        showTabMode('jpeg', 'single', false);
    } else {
        showTabMode('pdf', 'single', false);
    }

    function resetOutputDisplays() {
        if (validationResults) validationResults.style.display = 'none';
        if (bulkResultsBox) bulkResultsBox.style.display = 'none';
        if (emptyState) emptyState.style.display = 'block';
        if (statusAlert) statusAlert.style.display = 'none';
    }

    // Drag & Drop Zone Helper
    function setupDropZone(dropZoneId, fileInputId, fileHandler) {
        const dropZone = document.getElementById(dropZoneId);
        const fileInput = document.getElementById(fileInputId);
        if (!dropZone || !fileInput) return;

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('dragover');
            }, false);
        });

        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files && files.length > 0) {
                fileInput.files = files;
                if (fileHandler) fileHandler(files[0]);
            }
        });
    }

    // --- SINGLE PDF HANDLERS ---
    setupDropZone('dropZoneSingle', 'pdfFileInput', handleSingleFile);

    if (pdfFileInput) {
        pdfFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleSingleFile(e.target.files[0]);
            }
        });
    }

    async function handleSingleFile(file) {
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
            alert('Please select a valid PDF file.');
            return;
        }
        currentFile = file;
        if (fileInfo) fileInfo.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;

        const formData = new FormData();
        formData.append('file', file);
        showStatus('Analyzing PDF structure...', 'info');

        try {
            const resp = await fetch('/pdf/analyze', { method: 'POST', body: formData });
            const data = await resp.json();

            if (resp.ok) {
                if (analysisSection) analysisSection.style.display = 'block';
                if (modeBadge) modeBadge.textContent = data.mode;
                if (pagesCount) pagesCount.textContent = data.total_pages;
                if (imagesCount) imagesCount.textContent = data.total_images;
                if (vectorsCount) vectorsCount.textContent = data.total_drawings;

                if (data.candidate_fields && data.candidate_fields.length > 0 && fieldInputsContainer) {
                    fieldInputsContainer.innerHTML = '';
                    data.candidate_fields.slice(0, 4).forEach(cand => {
                        const label = cand.text.split(':')[0].trim();
                        if (label.length < 25) {
                            createFieldRow(label, '');
                        }
                    });
                }
                showStatus('PDF analyzed successfully.', 'success');
            } else {
                showStatus(`Analysis failed: ${data.detail || data.reason || 'Unknown error'}`, 'danger');
            }
        } catch (err) {
            showStatus(`Error analyzing PDF: ${err.message}`, 'danger');
        }
    }

    function createFieldRow(key = '', val = '') {
        if (!fieldInputsContainer) return;
        const row = document.createElement('div');
        row.className = 'field-row';
        row.innerHTML = `
            <input type="text" class="input-field key-input" placeholder="Field name (e.g. Name, Date)" value="${key}">
            <input type="text" class="input-field val-input" placeholder="New replacement value" value="${val}">
            <button class="btn-icon remove-row-btn">&times;</button>
        `;
        row.querySelector('.remove-row-btn').addEventListener('click', () => row.remove());
        fieldInputsContainer.appendChild(row);
    }

    if (addFieldBtn) addFieldBtn.addEventListener('click', () => createFieldRow());

    if (executeEditBtn) {
        executeEditBtn.addEventListener('click', async () => {
            if (!currentFile) {
                alert('Please upload a PDF template file first.');
                return;
            }

            const changes = {};
            if (fieldInputsContainer) {
                fieldInputsContainer.querySelectorAll('.field-row').forEach(row => {
                    const k = row.querySelector('.key-input').value.trim();
                    const v = row.querySelector('.val-input').value.trim();
                    if (k && v) changes[k] = v;
                });
            }

            const formData = new FormData();
            formData.append('file', currentFile);
            if (Object.keys(changes).length > 0) {
                formData.append('changes_json', JSON.stringify(changes));
            }

            const nlVal = nlInstruction ? nlInstruction.value.trim() : '';
            if (nlVal) formData.append('instruction', nlVal);

            if (Object.keys(changes).length === 0 && !nlVal) {
                alert('Please specify at least one field change or instruction.');
                return;
            }

            // Single Email Dispatch options
            if (singleSendEmailToggle && singleSendEmailToggle.checked) {
                const recipient = singleEmailRecipient ? singleEmailRecipient.value.trim() : '';
                if (!recipient || !recipient.includes('@')) {
                    alert('Please enter a valid email address in "Sent To".');
                    return;
                }
                formData.append('send_email', 'true');
                formData.append('recipient_email', recipient);
                if (singleEmailSubject) formData.append('email_subject', singleEmailSubject.value.trim());
                if (singleEmailBody) formData.append('email_body', singleEmailBody.value.trim());

                const senderEmail = document.getElementById('smtpSenderEmail') ? document.getElementById('smtpSenderEmail').value.trim() : '';
                const senderPass = document.getElementById('smtpSenderPassword') ? document.getElementById('smtpSenderPassword').value.trim() : '';
                const host = document.getElementById('smtpHost') ? document.getElementById('smtpHost').value.trim() : '';
                const port = document.getElementById('smtpPort') ? document.getElementById('smtpPort').value.trim() : '';

                if (senderEmail || senderPass) {
                    formData.append('smtp_json', JSON.stringify({
                        sender_email: senderEmail,
                        sender_password: senderPass,
                        host: host || 'smtp.hostinger.com',
                        port: parseInt(port) || 465
                    }));
                }
            }

            showStatus('Executing targeted mutation and running validation...', 'info');

            try {
                const resp = await fetch('/pdf/edit', { method: 'POST', body: formData });
                const data = await resp.json();

                if (resp.ok && data.success) {
                    if (emptyState) emptyState.style.display = 'none';
                    if (validationResults) validationResults.style.display = 'block';
                    if (bulkResultsBox) bulkResultsBox.style.display = 'none';
                    if (downloadBtn) {
                        downloadBtn.href = data.download_url;
                        downloadBtn.textContent = 'Download Edited PDF';
                    }

                    if (data.email_status) {
                        if (data.email_status.success) {
                            showStatus(`✅ Mutation completed & email sent to ${data.email_status.recipient}!`, 'success');
                        } else {
                            showStatus(`⚠️ Mutation completed, but email delivery failed: ${data.email_status.error}`, 'warning');
                        }
                    } else {
                        showStatus('Mutation completed & 100% validated!', 'success');
                    }
                } else {
                    if (validationResults) validationResults.style.display = 'none';
                    showStatus(`Mutation rejected: ${data.reason || data.message || 'Unsafe edit'}`, 'danger');
                }
            } catch (err) {
                showStatus(`Error executing edit: ${err.message}`, 'danger');
            }
        });
    }

    // --- BULK EXCEL/CSV HANDLERS ---
    async function handleBulkPdfFile(file) {
        bulkPdfFile = file;
        if (bulkPdfInfo) bulkPdfInfo.textContent = `PDF Template: ${bulkPdfFile.name}`;

        const formData = new FormData();
        formData.append('file', bulkPdfFile);
        try {
            const resp = await fetch('/pdf/analyze', { method: 'POST', body: formData });
            const data = await resp.json();
            if (resp.ok && data.text_spans) {
                const uniqueSpans = new Set();
                data.text_spans.forEach(s => {
                    const txt = s.text.trim();
                    if (txt.length >= 2 && txt.length < 35 && !uniqueSpans.has(txt)) {
                        uniqueSpans.add(txt);
                    }
                });
                detectedPdfFields = Array.from(uniqueSpans);
                updatePdfDatalist();
            }
        } catch (err) {
            console.error("PDF analysis failed", err);
        }
        renderBulkMappingRows();
    }

    async function handleBulkDataFile(file) {
        bulkDataFile = file;
        if (bulkDataInfo) bulkDataInfo.textContent = `Data File: ${bulkDataFile.name}`;

        const formData = new FormData();
        formData.append('file', bulkDataFile);
        showStatus('Reading Excel/CSV headers...', 'info');

        try {
            const resp = await fetch('/pdf/parse-columns', { method: 'POST', body: formData });
            const data = await resp.json();

            if (resp.ok && data.columns) {
                availableColumns = data.columns;
                populateEmailColSelect();
                showStatus(`Found ${availableColumns.length} columns in ${bulkDataFile.name}`, 'success');
                renderBulkMappingRows();
            } else {
                showStatus(`Failed to parse file headers: ${data.detail || 'Invalid format'}`, 'danger');
            }
        } catch (err) {
            showStatus(`Error reading columns: ${err.message}`, 'danger');
        }
    }

    setupDropZone('dropZoneBulkPdf', 'bulkPdfInput', handleBulkPdfFile);
    setupDropZone('dropZoneBulkData', 'bulkDataInput', handleBulkDataFile);

    if (bulkPdfInput) {
        bulkPdfInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) handleBulkPdfFile(e.target.files[0]);
        });
    }

    if (bulkDataInput) {
        bulkDataInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) handleBulkDataFile(e.target.files[0]);
        });
    }

    function updatePdfDatalist() {
        const datalist = document.getElementById('pdfDetectedDatalist');
        if (!datalist) return;
        datalist.innerHTML = '';
        detectedPdfFields.forEach(f => {
            const opt = document.createElement('option');
            opt.value = f;
            datalist.appendChild(opt);
        });
    }

    function populateEmailColSelect() {
        const jpegEmailColSelect = document.getElementById('jpegEmailColSelect');
        let optionsHtml = `<option value="">-- Select Email Column --</option>`;
        availableColumns.forEach(col => {
            const isEmailCol = col.toLowerCase().includes('email') || col.toLowerCase().includes('mail');
            const isSel = isEmailCol ? 'selected' : '';
            optionsHtml += `<option value="${col}" ${isSel}>${col}</option>`;
        });

        if (emailColSelect) emailColSelect.innerHTML = optionsHtml;
        if (jpegEmailColSelect) jpegEmailColSelect.innerHTML = optionsHtml;
    }

    function createBulkMapRow(pdfField = '', selectedCol = '') {
        if (!bulkMappingContainer) return;
        const row = document.createElement('div');
        row.className = 'field-row align-center';

        let colOptions = ``;
        if (availableColumns.length === 0) {
            colOptions = `<option value="">-- Upload Excel/CSV File First --</option>`;
        } else {
            colOptions = `<option value="">-- Select Excel Column --</option>`;
            availableColumns.forEach(col => {
                const isSelected = (col === selectedCol || col.toLowerCase() === pdfField.toLowerCase() || pdfField.toLowerCase().includes(col.toLowerCase())) ? 'selected' : '';
                colOptions += `<option value="${col}" ${isSelected}>${col}</option>`;
            });
        }

        row.innerHTML = `
            <input type="text" class="input-field target-pdf-field" placeholder="Target PDF field (e.g. Name, Date)" list="pdfDetectedDatalist" value="${pdfField}">
            <span class="mapping-arrow">➔</span>
            <select class="input-field excel-col-select">
                ${colOptions}
            </select>
            <button class="btn-icon remove-row-btn">&times;</button>
        `;

        row.querySelector('.remove-row-btn').addEventListener('click', () => row.remove());
        bulkMappingContainer.appendChild(row);
    }

    function renderBulkMappingRows() {
        if (!bulkMappingContainer) return;
        bulkMappingContainer.innerHTML = '';
        if (detectedPdfFields.length === 0) {
            createBulkMapRow('', '');
            return;
        }

        const fieldsToMap = detectedPdfFields.slice(0, 5);
        fieldsToMap.forEach(f => {
            const matchedCol = availableColumns.find(c => c.toLowerCase() === f.toLowerCase() || f.toLowerCase().includes(c.toLowerCase()) || c.toLowerCase().includes(f.toLowerCase())) || '';
            createBulkMapRow(f, matchedCol);
        });
    }

    renderBulkMappingRows();

    if (addBulkMapBtn) addBulkMapBtn.addEventListener('click', () => createBulkMapRow());

    if (executeBulkBtn) {
        executeBulkBtn.addEventListener('click', async () => {
            if (!bulkPdfFile) {
                alert('Please upload a base PDF template file.');
                return;
            }
            if (!bulkDataFile) {
                alert('Please upload an Excel (.xlsx) or CSV (.csv) data file.');
                return;
            }

            const mappings = {};
            if (bulkMappingContainer) {
                const rows = bulkMappingContainer.querySelectorAll('.field-row');
                rows.forEach(r => {
                    const pdfF = r.querySelector('.target-pdf-field').value.trim();
                    const colSel = r.querySelector('.excel-col-select').value.trim();
                    if (pdfF && colSel) {
                        mappings[pdfF] = colSel;
                    }
                });
            }

            const formData = new FormData();
            formData.append('pdf_file', bulkPdfFile);
            formData.append('data_file', bulkDataFile);
            if (Object.keys(mappings).length > 0) {
                formData.append('mappings_json', JSON.stringify(mappings));
            }

            // Email Dispatch options
            if (sendEmailToggle && sendEmailToggle.checked) {
                formData.append('send_email', 'true');
                const emailColVal = emailColSelect ? emailColSelect.value.trim() : '';
                if (!emailColVal) {
                    alert('Please select the Recipient Email Column from your Excel/CSV sheet.');
                    return;
                }
                formData.append('email_column', emailColVal);
                if (emailSubjectInput) formData.append('email_subject', emailSubjectInput.value.trim());
                if (emailBodyInput) formData.append('email_body', emailBodyInput.value.trim());

                const senderEmail = document.getElementById('smtpSenderEmail') ? document.getElementById('smtpSenderEmail').value.trim() : '';
                const senderPass = document.getElementById('smtpSenderPassword') ? document.getElementById('smtpSenderPassword').value.trim() : '';
                const host = document.getElementById('smtpHost') ? document.getElementById('smtpHost').value.trim() : '';
                const port = document.getElementById('smtpPort') ? document.getElementById('smtpPort').value.trim() : '';

                formData.append('smtp_json', JSON.stringify({
                    sender_email: senderEmail,
                    sender_password: senderPass,
                    host: host || 'smtp.hostinger.com',
                    port: parseInt(port) || 465
                }));
            }

            executeBulkBtn.disabled = true;
            showStatus('Submitting bulk job and running pre-flight verification...', 'info');

            try {
                const resp = await fetch('/pdf/edit-bulk', { method: 'POST', body: formData });
                const data = await resp.json();

                if (!resp.ok || !data.success) {
                    if (bulkResultsBox) bulkResultsBox.style.display = 'none';
                    showStatus(`Bulk submission failed: ${data.detail || data.reason || 'Processing error'}`, 'danger');
                    executeBulkBtn.disabled = false;
                    return;
                }

                // Job accepted — show progress container & start polling
                const pollUrl = data.poll_url;
                
                if (emptyState) emptyState.style.display = 'none';
                if (validationResults) validationResults.style.display = 'none';
                if (bulkResultsBox) bulkResultsBox.style.display = 'none';

                const bulkProgressContainer = document.getElementById('bulkProgressContainer');
                const bulkProgressBarFill = document.getElementById('bulkProgressBarFill');
                const bulkProgressPercentBadge = document.getElementById('bulkProgressPercentBadge');
                const bulkStepText = document.getElementById('bulkStepText');
                const bulkNextStepText = document.getElementById('bulkNextStepText');
                const bulkItemsCountText = document.getElementById('bulkItemsCountText');
                const bulkLiveActivityList = document.getElementById('bulkLiveActivityList');

                if (bulkProgressContainer) {
                    bulkProgressContainer.style.display = 'block';
                    if (bulkProgressBarFill) bulkProgressBarFill.style.width = '5%';
                    if (bulkProgressPercentBadge) bulkProgressPercentBadge.textContent = '5%';
                    if (bulkStepText) bulkStepText.textContent = 'Initializing background job & parsing data rows...';
                    if (bulkNextStepText) bulkNextStepText.textContent = 'Generating PDF for Candidate 1';
                    if (bulkItemsCountText) bulkItemsCountText.textContent = '0 items processed';
                    if (bulkLiveActivityList) bulkLiveActivityList.innerHTML = '';
                }

                showStatus('⚡ Bulk generation in progress... tracking live updates.', 'info');

                const pollInterval = setInterval(async () => {
                    try {
                        const statusResp = await fetch(pollUrl);
                        const statusData = await statusResp.json();

                        if (statusData.status === 'processing') {
                            const pct = statusData.progress_percent || 0;
                            if (bulkProgressBarFill) bulkProgressBarFill.style.width = `${pct}%`;
                            if (bulkProgressPercentBadge) bulkProgressPercentBadge.textContent = `${pct}%`;
                            if (bulkStepText && statusData.status_step) bulkStepText.textContent = statusData.status_step;
                            if (bulkNextStepText && statusData.next_step) bulkNextStepText.textContent = statusData.next_step;
                            if (bulkItemsCountText) bulkItemsCountText.textContent = `${statusData.current_row || 0} / ${statusData.total_rows || 0} candidates`;

                            if (bulkLiveActivityList && statusData.status_step && !bulkLiveActivityList.querySelector(`[data-step="${statusData.current_row}"]`)) {
                                const item = document.createElement('div');
                                item.className = 'live-activity-item';
                                item.setAttribute('data-step', statusData.current_row);
                                item.innerHTML = `<span>⚡ ${statusData.status_step}</span><span style="color: #60a5fa;">In Progress...</span>`;
                                bulkLiveActivityList.prepend(item);
                            }
                        } else if (statusData.status === 'done') {
                            clearInterval(pollInterval);
                            executeBulkBtn.disabled = false;

                            if (bulkProgressBarFill) bulkProgressBarFill.style.width = '100%';
                            if (bulkProgressPercentBadge) bulkProgressPercentBadge.textContent = '100%';
                            if (bulkStepText) bulkStepText.textContent = '✅ All candidate PDFs generated & dispatches completed!';
                            if (bulkNextStepText) bulkNextStepText.textContent = 'Complete - ZIP archive ready!';

                            setTimeout(() => {
                                if (bulkProgressContainer) bulkProgressContainer.style.display = 'none';
                                if (bulkResultsBox) bulkResultsBox.style.display = 'block';
                                if (downloadZipBtn) {
                                    downloadZipBtn.href = statusData.download_url;
                                    downloadZipBtn.textContent = 'Download All PDFs (.ZIP Archive)';
                                }

                                let summary = `Successfully generated <strong>${statusData.generated_count}</strong> of ${statusData.total_rows} customized PDFs!`;
                                if (sendEmailToggle && sendEmailToggle.checked) {
                                    if (statusData.sent_emails_count > 0) {
                                        summary += `<br>✅ Dispatched <strong>${statusData.sent_emails_count}</strong> individual emails successfully!`;
                                    }
                                    if (statusData.failed_emails_count > 0) {
                                        summary += `<br>❌ <strong>${statusData.failed_emails_count}</strong> email(s) failed:`;
                                        (statusData.email_errors || []).forEach(e => {
                                            summary += `<br>&nbsp;&nbsp;• Row ${e.row} (${e.recipient}): ${e.error}`;
                                        });
                                    }
                                    if (!statusData.sent_emails_count && !statusData.failed_emails_count) {
                                        summary += `<br>⚠️ No emails were sent. Check that the email column name matches your Excel/CSV header exactly.`;
                                    }

                                    if (statusData.failed_emails_count > 0 && statusData.sent_emails_count === 0) {
                                        showStatus(`⚠️ Generated ${statusData.generated_count} PDFs, but ALL ${statusData.failed_emails_count} emails failed to send!`, 'danger');
                                    } else if (statusData.failed_emails_count > 0) {
                                        showStatus(`⚠️ Generated ${statusData.generated_count} PDFs: ${statusData.sent_emails_count} emails sent, ${statusData.failed_emails_count} failed.`, 'warning');
                                    } else if (statusData.sent_emails_count > 0) {
                                        showStatus(`✅ ${statusData.generated_count} PDFs generated & ${statusData.sent_emails_count} emails dispatched successfully!`, 'success');
                                    } else {
                                        showStatus('✅ Bulk PDFs generated and ready for download!', 'success');
                                    }
                                } else {
                                    showStatus('✅ Bulk PDFs generated and ready for download!', 'success');
                                }
                                if (bulkSummaryText) bulkSummaryText.innerHTML = summary;
                            }, 1200);

                        } else if (statusData.status === 'failed') {
                            clearInterval(pollInterval);
                            executeBulkBtn.disabled = false;
                            if (bulkProgressContainer) bulkProgressContainer.style.display = 'none';
                            if (bulkResultsBox) bulkResultsBox.style.display = 'none';
                            showStatus(`❌ Bulk generation failed: ${statusData.error || 'Unknown error'}`, 'danger');
                        }
                    } catch (pollErr) {
                        clearInterval(pollInterval);
                        executeBulkBtn.disabled = false;
                        showStatus(`Error checking job status: ${pollErr.message}`, 'danger');
                    }
                }, 1000);

            } catch (err) {
                executeBulkBtn.disabled = false;
                showStatus(`Error during bulk generation: ${err.message}`, 'danger');
            }
        });
    }

    // Test SMTP Button Handler
    const testSmtpBtn = document.getElementById('testSmtpBtn');
    const testSmtpResult = document.getElementById('testSmtpResult');

    if (testSmtpBtn) {
        testSmtpBtn.addEventListener('click', async () => {
            const senderEmail = document.getElementById('smtpSenderEmail') ? document.getElementById('smtpSenderEmail').value.trim() : '';
            const senderPass = document.getElementById('smtpSenderPassword') ? document.getElementById('smtpSenderPassword').value.trim() : '';
            const host = document.getElementById('smtpHost') ? document.getElementById('smtpHost').value.trim() : '';
            const port = document.getElementById('smtpPort') ? document.getElementById('smtpPort').value.trim() : '';

            if (testSmtpResult) {
                testSmtpResult.style.color = '#e2e8f0';
                testSmtpResult.textContent = '⏳ Testing connection & sending test email...';
            }

            const formData = new FormData();
            if (senderEmail) formData.append('sender_email', senderEmail);
            if (senderPass) formData.append('sender_password', senderPass);
            if (host) formData.append('smtp_host', host);
            if (port) formData.append('smtp_port', port);
            formData.append('test_recipient', 'test@algoryx.in');

            try {
                const resp = await fetch('/pdf/test-smtp', { method: 'POST', body: formData });
                const data = await resp.json();
                if (testSmtpResult) {
                    if (resp.ok && data.success) {
                        testSmtpResult.style.color = '#4ade80';
                        testSmtpResult.textContent = `✅ ${data.message}`;
                    } else {
                        testSmtpResult.style.color = '#f87171';
                        testSmtpResult.textContent = `❌ ${data.error || 'Connection/Authentication failed'}`;
                    }
                }
            } catch (err) {
                if (testSmtpResult) {
                    testSmtpResult.style.color = '#f87171';
                    testSmtpResult.textContent = `❌ Test error: ${err.message}`;
                }
            }
        });
    }

    // ============================================================
    // JPEG EDITOR HANDLERS (SINGLE & BULK)
    // ============================================================

    let currentJpegFile = null;
    let bulkJpegTemplateFile = null;
    let bulkJpegDataFile = null;

    const jpegFileInput = document.getElementById('jpegFileInput');
    const jpegFileInfo = document.getElementById('jpegFileInfo');
    const jpegCanvasWrapper = document.getElementById('jpegCanvasWrapper');
    const jpegPreviewImg = document.getElementById('jpegPreviewImg');
    const coordPickerHint = document.getElementById('coordPickerHint');
    const coordBadge = document.getElementById('coordBadge');
    const jpegReplacementsContainer = document.getElementById('jpegReplacementsContainer');
    const addJpegRepBtn = document.getElementById('addJpegRepBtn');
    const jpegInsertionsContainer = document.getElementById('jpegInsertionsContainer');
    const addJpegInsBtn = document.getElementById('addJpegInsBtn');
    const executeJpegEditBtn = document.getElementById('executeJpegEditBtn');

    const jpegSingleSendEmailToggle = document.getElementById('jpegSingleSendEmailToggle');
    const jpegSingleEmailConfigBox = document.getElementById('jpegSingleEmailConfigBox');
    const jpegSingleEmailRecipient = document.getElementById('jpegSingleEmailRecipient');
    const jpegSingleEmailSubject = document.getElementById('jpegSingleEmailSubject');
    const jpegSingleEmailBody = document.getElementById('jpegSingleEmailBody');

    if (jpegSingleSendEmailToggle && jpegSingleEmailConfigBox) {
        jpegSingleSendEmailToggle.addEventListener('change', () => {
            jpegSingleEmailConfigBox.style.display = jpegSingleSendEmailToggle.checked ? 'block' : 'none';
        });
    }

    // Single JPEG Upload & Analysis
    setupDropZone('dropZoneJpegSingle', 'jpegFileInput', handleJpegSingleFile);

    if (jpegFileInput) {
        jpegFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleJpegSingleFile(e.target.files[0]);
            }
        });
    }

    async function handleJpegSingleFile(file) {
        currentJpegFile = file;
        if (jpegFileInfo) jpegFileInfo.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;

        // Show Image Preview
        if (jpegPreviewImg) {
            const reader = new FileReader();
            reader.onload = (e) => {
                jpegPreviewImg.src = e.target.result;
                if (jpegCanvasWrapper) jpegCanvasWrapper.style.display = 'block';
                if (coordPickerHint) coordPickerHint.style.display = 'flex';
            };
            reader.readAsDataURL(file);
        }

        const formData = new FormData();
        formData.append('file', file);
        showStatus('Analyzing JPEG image & detecting text regions...', 'info');

        try {
            const resp = await fetch('/jpeg/analyze', { method: 'POST', body: formData });
            const data = await resp.json();

            if (resp.ok && data.success) {
                if (data.detected_fields && data.detected_fields.length > 0 && jpegReplacementsContainer) {
                    jpegReplacementsContainer.innerHTML = '';
                    const fieldsToSuggest = data.detected_fields.slice(0, 5);
                    fieldsToSuggest.forEach(f => {
                        createJpegRepRow(f.text, '');
                    });
                }
                showStatus(`JPEG analyzed successfully! (${data.width}x${data.height} px)`, 'success');
            } else {
                showStatus(`JPEG analysis complete.`, 'info');
            }
        } catch (err) {
            showStatus(`Error analyzing JPEG: ${err.message}`, 'danger');
        }
    }

    // Interactive Canvas Image Click Handler (X, Y Picker)
    if (jpegPreviewImg) {
        jpegPreviewImg.addEventListener('click', (e) => {
            const rect = jpegPreviewImg.getBoundingClientRect();
            const renderedWidth = rect.width;
            const renderedHeight = rect.height;
            const naturalWidth = jpegPreviewImg.naturalWidth || renderedWidth;
            const naturalHeight = jpegPreviewImg.naturalHeight || renderedHeight;

            const clickX = e.clientX - rect.left;
            const clickY = e.clientY - rect.top;

            const realX = Math.round(clickX * (naturalWidth / renderedWidth));
            const realY = Math.round(clickY * (naturalHeight / renderedHeight));

            if (coordBadge) coordBadge.textContent = `X: ${realX}, Y: ${realY}`;

            // Pre-fill a new free-space insertion row with clicked coordinates
            createJpegInsRow(realX, realY, '', '', '#000000');
            showStatus(`🎯 Selected coordinate (${realX}, ${realY}) added to Free-Space Insertions!`, 'info');
        });
    }

    function createJpegRepRow(target = '', val = '') {
        if (!jpegReplacementsContainer) return;
        const row = document.createElement('div');
        row.className = 'field-row';
        row.innerHTML = `
            <input type="text" class="input-field key-input jpeg-target-input" placeholder="Existing text in JPEG to replace" value="${target}">
            <input type="text" class="input-field val-input jpeg-val-input" placeholder="New replacement value" value="${val}">
            <button class="btn-icon remove-row-btn">&times;</button>
        `;
        row.querySelector('.remove-row-btn').addEventListener('click', () => row.remove());
        jpegReplacementsContainer.appendChild(row);
    }

    function createJpegInsRow(x = '', y = '', text = '', size = '', color = '#000000') {
        if (!jpegInsertionsContainer) return;
        const row = document.createElement('div');
        row.className = 'ins-grid';
        row.innerHTML = `
            <input type="number" class="input-field ins-x" placeholder="X px" value="${x}">
            <input type="number" class="input-field ins-y" placeholder="Y px" value="${y}">
            <input type="text" class="input-field ins-text" placeholder="Value to insert" value="${text}">
            <input type="number" class="input-field ins-size" placeholder="Size" value="${size}">
            <input type="color" class="input-field ins-color" value="${color}" style="padding: 2px;">
            <button class="btn-icon remove-row-btn">&times;</button>
        `;
        row.querySelector('.remove-row-btn').addEventListener('click', () => row.remove());
        jpegInsertionsContainer.appendChild(row);
    }

    if (addJpegRepBtn) addJpegRepBtn.addEventListener('click', () => createJpegRepRow());
    if (addJpegInsBtn) addJpegInsBtn.addEventListener('click', () => createJpegInsRow());

    // Execute Single JPEG Edit
    if (executeJpegEditBtn) {
        executeJpegEditBtn.addEventListener('click', async () => {
            if (!currentJpegFile) {
                alert('Please upload a JPEG image template first.');
                return;
            }

            const replacements = [];
            if (jpegReplacementsContainer) {
                jpegReplacementsContainer.querySelectorAll('.field-row').forEach(r => {
                    const target = r.querySelector('.jpeg-target-input').value.trim();
                    const val = r.querySelector('.jpeg-val-input').value.trim();
                    if (target && val) {
                        replacements.push({ target, new_value: val });
                    }
                });
            }

            const insertions = [];
            if (jpegInsertionsContainer) {
                jpegInsertionsContainer.querySelectorAll('.ins-grid').forEach(r => {
                    const xVal = r.querySelector('.ins-x').value.trim();
                    const yVal = r.querySelector('.ins-y').value.trim();
                    const textVal = r.querySelector('.ins-text').value.trim();
                    const sizeVal = r.querySelector('.ins-size').value.trim();
                    const colorVal = r.querySelector('.ins-color').value.trim();

                    if (textVal && (xVal !== '' || yVal !== '')) {
                        insertions.push({
                            x: parseInt(xVal) || 0,
                            y: parseInt(yVal) || 0,
                            text: textVal,
                            font_size: sizeVal ? parseInt(sizeVal) : null,
                            font_color: colorVal
                        });
                    }
                });
            }

            if (replacements.length === 0 && insertions.length === 0) {
                alert('Please specify at least one text replacement or free-space text insertion.');
                return;
            }

            const formData = new FormData();
            formData.append('file', currentJpegFile);
            if (replacements.length > 0) formData.append('replacements_json', JSON.stringify(replacements));
            if (insertions.length > 0) formData.append('insertions_json', JSON.stringify(insertions));

            if (jpegSingleSendEmailToggle && jpegSingleSendEmailToggle.checked) {
                const recipient = jpegSingleEmailRecipient ? jpegSingleEmailRecipient.value.trim() : '';
                if (!recipient || !recipient.includes('@')) {
                    alert('Please enter a valid email address.');
                    return;
                }
                formData.append('send_email', 'true');
                formData.append('recipient_email', recipient);
                if (jpegSingleEmailSubject) formData.append('email_subject', jpegSingleEmailSubject.value.trim());
                if (jpegSingleEmailBody) formData.append('email_body', jpegSingleEmailBody.value.trim());

                const senderEmail = document.getElementById('smtpSenderEmail') ? document.getElementById('smtpSenderEmail').value.trim() : '';
                const senderPass = document.getElementById('smtpSenderPassword') ? document.getElementById('smtpSenderPassword').value.trim() : '';
                const host = document.getElementById('smtpHost') ? document.getElementById('smtpHost').value.trim() : '';
                const port = document.getElementById('smtpPort') ? document.getElementById('smtpPort').value.trim() : '';

                formData.append('smtp_json', JSON.stringify({
                    sender_email: senderEmail,
                    sender_password: senderPass,
                    host: host || 'smtp.hostinger.com',
                    port: parseInt(port) || 465
                }));
            }

            showStatus('Editing JPEG image and rendering output...', 'info');

            try {
                const resp = await fetch('/jpeg/edit', { method: 'POST', body: formData });
                const data = await resp.json();

                if (resp.ok && data.success) {
                    if (emptyState) emptyState.style.display = 'none';
                    if (validationResults) validationResults.style.display = 'block';
                    if (bulkResultsBox) bulkResultsBox.style.display = 'none';
                    if (downloadBtn) {
                        downloadBtn.href = data.download_url;
                        downloadBtn.textContent = 'Download Edited JPEG';
                    }

                    if (data.email_status) {
                        if (data.email_status.success) {
                            showStatus(`✅ JPEG edit complete & emailed to ${data.email_status.recipient}!`, 'success');
                        } else {
                            showStatus(`⚠️ JPEG edit complete, but email delivery failed: ${data.email_status.error}`, 'warning');
                        }
                    } else {
                        showStatus('✅ JPEG edit complete & rendered successfully!', 'success');
                    }
                } else {
                    showStatus(`JPEG Edit Failed: ${data.detail || data.reason || 'Processing error'}`, 'danger');
                }
            } catch (err) {
                showStatus(`Error editing JPEG: ${err.message}`, 'danger');
            }
        });
    }

    // --- Bulk JPEG Handlers ---
    const jpegBulkTemplateInput = document.getElementById('jpegBulkTemplateInput');
    const jpegBulkTemplateInfo = document.getElementById('jpegBulkTemplateInfo');
    const jpegBulkDataInput = document.getElementById('jpegBulkDataInput');
    const jpegBulkDataInfo = document.getElementById('jpegBulkDataInfo');
    const jpegBulkMappingContainer = document.getElementById('jpegBulkMappingContainer');
    const addJpegBulkMapBtn = document.getElementById('addJpegBulkMapBtn');
    const executeJpegBulkBtn = document.getElementById('executeJpegBulkBtn');

    const jpegSendEmailToggle = document.getElementById('jpegSendEmailToggle');
    const jpegEmailConfigBox = document.getElementById('jpegEmailConfigBox');
    const jpegEmailColSelect = document.getElementById('jpegEmailColSelect');
    const jpegEmailSubjectInput = document.getElementById('jpegEmailSubjectInput');
    const jpegEmailBodyInput = document.getElementById('jpegEmailBodyInput');

    if (jpegSendEmailToggle && jpegEmailConfigBox) {
        jpegSendEmailToggle.addEventListener('change', () => {
            jpegEmailConfigBox.style.display = jpegSendEmailToggle.checked ? 'block' : 'none';
        });
    }

    function handleJpegBulkTemplateFile(file) {
        bulkJpegTemplateFile = file;
        if (jpegBulkTemplateInfo) jpegBulkTemplateInfo.textContent = `JPEG Template: ${bulkJpegTemplateFile.name}`;
    }

    async function handleJpegBulkDataFile(file) {
        bulkJpegDataFile = file;
        if (jpegBulkDataInfo) jpegBulkDataInfo.textContent = `Data File: ${bulkJpegDataFile.name}`;

        const formData = new FormData();
        formData.append('file', bulkJpegDataFile);
        showStatus('Reading Excel/CSV headers...', 'info');

        try {
            const resp = await fetch('/pdf/parse-columns', { method: 'POST', body: formData });
            const data = await resp.json();

            if (resp.ok && data.columns) {
                availableColumns = data.columns;
                populateEmailColSelect();
                createJpegBulkMapRow();
                showStatus(`Found ${availableColumns.length} columns in ${bulkJpegDataFile.name}`, 'success');
            }
        } catch (err) {
            showStatus(`Error reading columns: ${err.message}`, 'danger');
        }
    }

    setupDropZone('dropZoneJpegBulkTemplate', 'jpegBulkTemplateInput', handleJpegBulkTemplateFile);
    setupDropZone('dropZoneJpegBulkData', 'jpegBulkDataInput', handleJpegBulkDataFile);

    if (jpegBulkTemplateInput) {
        jpegBulkTemplateInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleJpegBulkTemplateFile(e.target.files[0]);
            }
        });
    }

    if (jpegBulkDataInput) {
        jpegBulkDataInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleJpegBulkDataFile(e.target.files[0]);
            }
        });
    }

    function createJpegBulkMapRow(field = '', col = '') {
        if (!jpegBulkMappingContainer) return;
        const row = document.createElement('div');
        row.className = 'field-row align-center';

        let colOptions = availableColumns.length === 0
            ? `<option value="">-- Upload Excel/CSV File First --</option>`
            : `<option value="">-- Select Excel Column --</option>` + availableColumns.map(c => `<option value="${c}" ${c === col ? 'selected' : ''}>${c}</option>`).join('');

        row.innerHTML = `
            <input type="text" class="input-field jpeg-bulk-field" placeholder="Target Field OR (X,Y) e.g. Name or 150,300" value="${field}">
            <span class="mapping-arrow">➔</span>
            <select class="input-field jpeg-bulk-col">
                ${colOptions}
            </select>
            <button class="btn-icon remove-row-btn">&times;</button>
        `;
        row.querySelector('.remove-row-btn').addEventListener('click', () => row.remove());
        jpegBulkMappingContainer.appendChild(row);
    }

    if (addJpegBulkMapBtn) addJpegBulkMapBtn.addEventListener('click', () => createJpegBulkMapRow());

    if (executeJpegBulkBtn) {
        executeJpegBulkBtn.addEventListener('click', async () => {
            if (!bulkJpegTemplateFile) {
                alert('Please upload a base JPEG template image.');
                return;
            }
            if (!bulkJpegDataFile) {
                alert('Please upload an Excel (.xlsx) or CSV (.csv) file.');
                return;
            }

            const mappings = [];
            if (jpegBulkMappingContainer) {
                jpegBulkMappingContainer.querySelectorAll('.field-row').forEach(r => {
                    const targetVal = r.querySelector('.jpeg-bulk-field').value.trim();
                    const colVal = r.querySelector('.jpeg-bulk-col').value.trim();

                    if (targetVal && colVal) {
                        if (targetVal.includes(',')) {
                            const parts = targetVal.split(',');
                            mappings.push({
                                x: parseInt(parts[0]) || 0,
                                y: parseInt(parts[1]) || 0,
                                excel_column: colVal,
                                is_free_space: true
                            });
                        } else {
                            mappings.push({
                                field: targetVal,
                                excel_column: colVal,
                                is_free_space: false
                            });
                        }
                    }
                });
            }

            const formData = new FormData();
            formData.append('jpeg_file', bulkJpegTemplateFile);
            formData.append('data_file', bulkJpegDataFile);
            formData.append('mappings_json', JSON.stringify(mappings));

            if (jpegSendEmailToggle && jpegSendEmailToggle.checked) {
                const emailColVal = jpegEmailColSelect ? jpegEmailColSelect.value.trim() : '';
                if (!emailColVal) {
                    alert('Please select the Recipient Email Column from your Excel/CSV sheet.');
                    return;
                }
                formData.append('send_email', 'true');
                formData.append('email_column', emailColVal);
                if (jpegEmailSubjectInput) formData.append('email_subject', jpegEmailSubjectInput.value.trim());
                if (jpegEmailBodyInput) formData.append('email_body', jpegEmailBodyInput.value.trim());

                const senderEmail = document.getElementById('smtpSenderEmail') ? document.getElementById('smtpSenderEmail').value.trim() : '';
                const senderPass = document.getElementById('smtpSenderPassword') ? document.getElementById('smtpSenderPassword').value.trim() : '';
                const host = document.getElementById('smtpHost') ? document.getElementById('smtpHost').value.trim() : '';
                const port = document.getElementById('smtpPort') ? document.getElementById('smtpPort').value.trim() : '';

                formData.append('smtp_json', JSON.stringify({
                    sender_email: senderEmail,
                    sender_password: senderPass,
                    host: host || 'smtp.hostinger.com',
                    port: parseInt(port) || 465
                }));
            }

            executeJpegBulkBtn.disabled = true;
            showStatus('Starting bulk JPEG generation background job...', 'info');

            try {
                const resp = await fetch('/jpeg/edit-bulk', { method: 'POST', body: formData });
                const data = await resp.json();

                if (!resp.ok || !data.success) {
                    showStatus(`Bulk JPEG submission failed: ${data.detail || data.reason}`, 'danger');
                    executeJpegBulkBtn.disabled = false;
                    return;
                }

                const pollUrl = data.poll_url;

                if (emptyState) emptyState.style.display = 'none';
                if (validationResults) validationResults.style.display = 'none';
                if (bulkResultsBox) bulkResultsBox.style.display = 'none';

                const bulkProgressContainer = document.getElementById('bulkProgressContainer');
                const bulkProgressBarFill = document.getElementById('bulkProgressBarFill');
                const bulkProgressPercentBadge = document.getElementById('bulkProgressPercentBadge');
                const bulkStepText = document.getElementById('bulkStepText');

                if (bulkProgressContainer) {
                    bulkProgressContainer.style.display = 'block';
                    if (bulkProgressBarFill) bulkProgressBarFill.style.width = '10%';
                    if (bulkProgressPercentBadge) bulkProgressPercentBadge.textContent = '10%';
                    if (bulkStepText) bulkStepText.textContent = 'Processing bulk JPEG images...';
                }

                const pollInterval = setInterval(async () => {
                    try {
                        const statusResp = await fetch(pollUrl);
                        const statusData = await statusResp.json();

                        if (statusData.status === 'processing') {
                            const pct = statusData.progress_percent || 0;
                            if (bulkProgressBarFill) bulkProgressBarFill.style.width = `${pct}%`;
                            if (bulkProgressPercentBadge) bulkProgressPercentBadge.textContent = `${pct}%`;
                            if (bulkStepText && statusData.status_step) bulkStepText.textContent = statusData.status_step;
                        } else if (statusData.status === 'done') {
                            clearInterval(pollInterval);
                            executeJpegBulkBtn.disabled = false;

                            if (bulkProgressContainer) bulkProgressContainer.style.display = 'none';
                            if (bulkResultsBox) bulkResultsBox.style.display = 'block';
                            if (downloadZipBtn) {
                                downloadZipBtn.href = statusData.download_url;
                                downloadZipBtn.textContent = 'Download All JPEGs (.ZIP Archive)';
                            }

                            if (bulkSummaryText) bulkSummaryText.innerHTML = `Successfully generated <strong>${statusData.generated_count}</strong> of ${statusData.total_rows} customized JPEGs!`;
                            showStatus('✅ Bulk JPEGs generated and ready for download!', 'success');
                        } else if (statusData.status === 'failed') {
                            clearInterval(pollInterval);
                            executeJpegBulkBtn.disabled = false;
                            showStatus(`❌ Bulk JPEG generation failed: ${statusData.error}`, 'danger');
                        }
                    } catch (err) {
                        clearInterval(pollInterval);
                        executeJpegBulkBtn.disabled = false;
                    }
                }, 1000);

            } catch (err) {
                executeJpegBulkBtn.disabled = false;
                showStatus(`Error during bulk JPEG generation: ${err.message}`, 'danger');
            }
        });
    }

    function showStatus(msg, type) {
        if (!statusAlert || !statusText) return;
        statusAlert.style.display = 'block';
        statusAlert.className = `status-alert ${type}`;
        statusText.textContent = msg;
    }
});
