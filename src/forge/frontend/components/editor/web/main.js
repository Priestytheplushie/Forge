

require.config({ paths: { 'vs': 'vs' } });

let editor;
let bridge;
let diff_bridge;
let isEditorModelReady = false;
let isPyForgeSessionActive = false;
const pending_completions = new Map();
const pending_hovers = new Map();
const pending_code_actions = new Map();
const pending_codelens = new Map();
const pending_conflict_checks = new Map();
let currentMergeDecorations = [];
let diffChanges = [];
let currentDiffIndex = -1;
let semanticTokenProviderHandle = null;
let contentChangeListener = null;
let modelSetListener = null;


function log(msg, ...args) { console.log(`[JS] ${msg}`, ...args); }
function warn(msg, ...args) { console.warn(`[JS] ${msg}`, ...args); }
function err(msg, ...args) { console.error(`[JS] ${msg}`, ...args); }


function isDiffEditorInstance(ed) { return ed && typeof ed.getModifiedEditor === "function"; }
function getActiveModel() {
    if (!editor) return null;
    if (isDiffEditorInstance(editor)) {
        const mod = editor.getModifiedEditor();
        return mod ? mod.getModel() : null;
    }
    return editor.getModel();
}
function disposeModel(model) { if (model && typeof model.dispose === 'function') { try { model.dispose(); } catch (e) { warn('Model dispose failed', e); } } }
function disposeListener(listener) { if (listener && typeof listener.dispose === 'function') { try { listener.dispose(); } catch (e) { warn('Listener dispose failed', e); } } }
function getConflictRegex() { return new RegExp("(<<<<<<< HEAD\\r?\\n)([\\s\\S]*?)(=======)(\\r?\\n[\\s\\S]*?)(>>>>>>> [\\s\\S]*?(\\r?\\n)?)", 'g'); }



function init() {
    log('Bridge is ready, initializing Monaco...');


    monaco.languages.registerCompletionItemProvider('python', {
        provideCompletionItems: (model, position) => {
            if (!model || (model.uri.scheme !== 'file' && model.uri.scheme !== 'untitled') || !isEditorModelReady || !bridge) { return { suggestions: [] }; }
            const uri = model.uri.toString();
            const callback_id = `completion-${Date.now()}-${Math.random()}`;
            return new Promise(resolve => {
                pending_completions.set(callback_id, resolve);
                try { bridge.request_completions(callback_id, uri, position.lineNumber, position.column); }
                catch (e) { warn('request_completions failed', e); resolve({ suggestions: [] }); pending_completions.delete(callback_id); }
            });
        }
    });


    monaco.languages.registerHoverProvider('python', {
        provideHover: (model, position) => {
            if (!model || (model.uri.scheme !== 'file' && model.uri.scheme !== 'untitled') || !isEditorModelReady || !bridge) { return null; }
            const uri = model.uri.toString();
            const callback_id = `hover-${Date.now()}-${Math.random()}`;
            return new Promise(resolve => {
                pending_hovers.set(callback_id, resolve);
                try { bridge.request_hover(callback_id, uri, position.lineNumber, position.column); }
                catch (e) { warn('request_hover failed', e); resolve(null); pending_hovers.delete(callback_id); }
            });
        }
    });


    monaco.languages.registerCodeActionProvider('python', {
        provideCodeActions: (model, range, context, token) => {
            if (!bridge) return { actions: [], dispose: () => {} };
            const callback_id = `codeaction-${Date.now()}-${Math.random()}`;
            const range_data = { start: { line: range.startLineNumber-1, character: range.startColumn-1 }, end: { line: range.endLineNumber-1, character: range.endColumn-1 } };
            return new Promise(resolve => {
                pending_code_actions.set(callback_id, resolve);
                try { bridge.request_code_actions(callback_id, model.uri.toString(), range_data, context.markers); }
                catch (e) { warn('request_code_actions failed', e); resolve({ actions: [], dispose: () => {} }); pending_code_actions.delete(callback_id); }
            });
        }
    });


    monaco.languages.registerCodeLensProvider('python', {
        provideCodeLenses: (model, token) => {
             if (!bridge || !model.uri.toString().endsWith('.pfscript')) return { lenses: [], dispose: () => {} };
             const callback_id = `codelens-${Date.now()}-${Math.random()}`;
             return new Promise(resolve => {
                pending_codelens.set(callback_id, resolve);
                try { bridge.request_codelens(callback_id, model.uri.toString()); }
                catch (e) { warn('request_codelens failed', e); resolve({ lenses: [], dispose: () => {} }); pending_codelens.delete(callback_id); }
             });
        }
    });


    monaco.languages.registerCodeLensProvider('*', {
        provideCodeLenses: function (model) {
            if (!model || !model.isMergeConflict) return { lenses: [] };
            const content = model.getValue();
            const regex = getConflictRegex();
            let match; const lenses = [];
            while ((match = regex.exec(content)) !== null) {
                const startLine = model.getPositionAt(match.index).lineNumber;
                const range = { startLineNumber: startLine, startColumn: 1, endLineNumber: startLine, endColumn: 1 };
                lenses.push(
                    { range, command: { title: 'Accept Current', id: 'merge.acceptCurrent', arguments: [range] } },
                    { range, command: { title: 'Accept Incoming', id: 'merge.acceptIncoming', arguments: [range] } },
                    { range, command: { title: 'Accept Both', id: 'merge.acceptBoth', arguments: [range] } }
                );
            }
            return { lenses, dispose: () => {} };
        }
    });


    monaco.editor.registerCommand('merge.acceptCurrent', (accessor, range) => { accept_merge('current', range); });
    monaco.editor.registerCommand('merge.acceptIncoming', (accessor, range) => { accept_merge('incoming', range); });
    monaco.editor.registerCommand('merge.acceptBoth', (accessor, range) => { accept_merge('both', range); });
    monaco.editor.registerCommand('forge.goToNextChange', () => go_to_next_change());
    monaco.editor.registerCommand('forge.goToPreviousChange', () => go_to_previous_change());

        monaco.editor.registerCommand('pyforge.runScript', () => {
        if(bridge) { bridge.on_run_script_requested(); }
    });
    monaco.editor.registerCommand('forge.validateMasterScript', () => {
        if(bridge) { bridge.on_validate_master_script(); }
    });


    log('All providers and commands registered.');
}

require(['vs/editor/editor.main'], function () {
    log('Monaco loader has finished.');

        if (typeof QWebChannel !== 'undefined' && typeof qt !== 'undefined' && qt.webChannelTransport) {
        new QWebChannel(qt.webChannelTransport, function (channel) {
            log('QWebChannel has connected successfully.');
            bridge = channel.objects?.bridge;
            diff_bridge = channel.objects?.diff_bridge;

            if (bridge) {
                log('Standard editor bridge found. Signaling ready to Python.');
                try { bridge.on_web_channel_ready(); } catch (e) { warn('bridge.on_web_channel_ready failed', e); }
            } else if (diff_bridge) {
                log('Diff editor bridge found. Signaling ready to Python.');
                try { diff_bridge.on_web_channel_ready(); } catch (e) { warn('diff_bridge.on_web_channel_ready failed', e); }
            } else {
                err('CRITICAL: No valid bridge object (bridge/diff_bridge) found.');
            }
        });
    } else {
        warn('QWebChannel or qt.webChannelTransport not available');
    }
});

function set_pyforge_session_active(active) {
    if (isPyForgeSessionActive !== active) {
        isPyForgeSessionActive = active;
        const model = getActiveModel();
        if (model && model.uri.toString().endsWith('.pfscript')) {

            const content = model.getValue();
            model.setValue('');
            model.setValue(content);
        }
    }
}

function initialize_editor(themeData, isDiffEditor = false) {
    if (!monaco) { warn('Monaco not loaded'); return; }
    if (editor) { try { if (typeof editor.dispose === 'function') { editor.dispose(); } } catch (e) { warn('Editor dispose failed', e); } }
    if (themeData) { try { monaco.editor.defineTheme('forge-theme', themeData); monaco.editor.setTheme('forge-theme'); } catch (e) { warn('Theme definition failed', e); } }
    const editorOptions = { 'semanticHighlighting.enabled': true, readOnlyMessage: { value: '' } };
    if (isDiffEditor) {
        editor = monaco.editor.createDiffEditor(document.getElementById('container'), { ...editorOptions, originalEditable: false, readOnly: true });
        editor.onDidUpdateDiff(() => { diffChanges = editor.getLineChanges() || []; currentDiffIndex = -1; });
        const addStageAction = (ed, isModified) => {
            if (!ed || typeof ed.addAction !== 'function') return;
            ed.addAction({
                id: `forge-stage-lines-${isModified ? 'modified' : 'original'}`,
                label: 'Stage Selected Lines', contextMenuGroupId: '9_cutcopypaste', contextMenuOrder: 1.6, precondition: 'editorHasSelection',
                run: function(e) {
                    if (diff_bridge) {
                        const selection = e.getSelection(); const model = e.getModel();
                        if (model && selection) {
                            const text = model.getValueInRange(selection);
                            const prefix = isModified ? '+' : '-';
                            const hunk = text.split('\n').map(line => prefix + line).join('\n');
                            try { diff_bridge.on_stage_lines(hunk); } catch (err) { warn('diff_bridge.on_stage_lines failed', err); }
                        }
                    }
                }
            });
        };
        addStageAction(editor.getOriginalEditor(), false);
        addStageAction(editor.getModifiedEditor(), true);
        if (diff_bridge) { try { diff_bridge.js_loaded(); } catch (e) { warn('diff_bridge.js_loaded failed', e); } }
    } else {
        editor = monaco.editor.create(document.getElementById('container'), { ...editorOptions, language: 'plaintext', quickSuggestions: true, hover: { enabled: true }, codeLens: true });
        editor.onDidChangeModelContent(() => { if (getActiveModel()?.isMergeConflict) { update_merge_decorations(); } });
        editor.addAction({ 
            id: 'forge-stage-lines-normal', label: 'Stage Selected Lines', contextMenuGroupId: '9_cutcopypaste', contextMenuOrder: 1.6, precondition: 'editorHasSelection', 
            run: function(ed) {
                if (bridge) {
                    const selection = ed.getSelection(); const model = getActiveModel();
                    if (model && selection) {
                        const text = model.getValueInRange(selection);
                        const hunk = text.split('\n').map(line => '+' + line).join('\n');
                        try { bridge.on_stage_lines(hunk); } catch (e) { warn('bridge.on_stage_lines failed', e); }
                    }
                }
            }
        });
        editor.addAction({ 
            id: 'forge-apply-staged-changes', label: 'Apply Staged Changes', contextMenuGroupId: '9_cutcopypaste', contextMenuOrder: 1.7, 
            run: function(ed) { if (bridge) { try { bridge.on_apply_staged_changes(); } catch (e) { warn('bridge.on_apply_staged_changes failed', e); } } } 
        });
        editor.onDidChangeCursorPosition(e => { if (bridge && e.position) { try { bridge.on_cursor_position_changed(e.position.lineNumber, e.position.column); } catch (err) { warn('on_cursor_position_changed failed', err); } } });
        if (bridge) {
            const connectSignal = (signal, action) => { try { if (signal && typeof signal.connect === 'function') { signal.connect(() => editor.trigger('keyboard', action, null)); } } catch (e) { warn(`Failed to connect ${action} signal`, e); } };
            connectSignal(bridge.undo_requested, 'undo'); connectSignal(bridge.redo_requested, 'redo'); connectSignal(bridge.cut_requested, 'cut'); connectSignal(bridge.copy_requested, 'copy'); connectSignal(bridge.paste_requested, 'paste');
        }
        if (bridge) { init(); try { bridge.js_loaded(); } catch (e) { warn('bridge.js_loaded failed', e); } }
    }
}

function enter_merge_mode() { const model = getActiveModel(); if (model) { model.isMergeConflict = true; update_merge_decorations(); } }
function exit_merge_mode() { const model = getActiveModel(); if (editor && model) { model.isMergeConflict = false; if (!isDiffEditorInstance(editor)) { currentMergeDecorations = editor.deltaDecorations(currentMergeDecorations, []); } } }
function update_merge_decorations() {
    const model = getActiveModel(); if (!editor || !model) return;
    const content = model.getValue(); const regex = getConflictRegex(); regex.lastIndex = 0; let match; const newDecorations = [];
    while ((match = regex.exec(content)) !== null) {
        const startPos = model.getPositionAt(match.index); const currentLines = match[2].split('\n').length; const incomingLines = match[4].split('\n').length;
        newDecorations.push({ range: new monaco.Range(startPos.lineNumber + 1, 1, startPos.lineNumber + 1 + currentLines - 1, 1), options: { isWholeLine: true, className: 'merge-current-content' } });
        const incomingStartLine = model.getPositionAt(match.index + match[1].length + match[2].length + match[3].length).lineNumber;
        newDecorations.push({ range: new monaco.Range(incomingStartLine + 1, 1, incomingStartLine + incomingLines - 1, 1), options: { isWholeLine: true, className: 'merge-incoming-content' } });
    }
    if (!isDiffEditorInstance(editor)) { currentMergeDecorations = editor.deltaDecorations(currentMergeDecorations, newDecorations); }
}
function accept_merge(type, conflictRange) {
    const model = getActiveModel(); if (!editor || !model || !conflictRange) return;
    const content = model.getValue(); const regex = getConflictRegex(); regex.lastIndex = 0; let match; let targetMatch = null;
    while ((match = regex.exec(content)) !== null) {
        const startPos = model.getPositionAt(match.index); const endPos = model.getPositionAt(match.index + match[0].length);
        if (conflictRange.startLineNumber >= startPos.lineNumber && conflictRange.startLineNumber <= endPos.lineNumber) { targetMatch = match; break; }
    }
    if (!targetMatch) return;
    const currentContent = targetMatch[2].trim(); const incomingContent = targetMatch[4].substring(targetMatch[4].indexOf('\n') + 1).trim(); let resolvedText;
    if (type === 'current') resolvedText = currentContent;
    else if (type === 'incoming') resolvedText = incomingContent;
    else if (type === 'both') resolvedText = currentContent + '\n' + incomingContent;
    else return;
    const startPos = model.getPositionAt(targetMatch.index); const endPos = model.getPositionAt(targetMatch.index + targetMatch[0].length);
    const range = new monaco.Range(startPos.lineNumber, startPos.column, endPos.lineNumber, endPos.column);
    const op = { range: range, text: resolvedText };
    model.pushEditOperations([], [op], () => null); update_merge_decorations();
}
function check_for_conflicts(callback_id) {
    if (!bridge) { warn('check_for_conflicts called before bridge was ready.'); return; }
    const model = getActiveModel();
    if (!model) { try { bridge.receive_conflict_check_result(callback_id, false); } catch (e) { warn('bridge.receive_conflict_check_result failed', e); } return; }
    const hasConflicts = model.getValue().includes('<<<<<<<');
    try { bridge.receive_conflict_check_result(callback_id, hasConflicts); } catch (e) { warn('bridge.receive_conflict_check_result failed', e); }
}
function set_theme(themeData) { if (monaco && themeData) { try { monaco.editor.defineTheme('forge-theme', themeData); monaco.editor.setTheme('forge-theme'); } catch (e) { warn('Failed to set theme', e); } } }
function set_diff_content(original_content, modified_content, original_label, modified_label) {
    if (!editor || !isDiffEditorInstance(editor)) return;
    try {
        const originalModel = monaco.editor.createModel(original_content || '', 'python', monaco.Uri.parse(`inmemory://model/original/${original_label}`));
        const modifiedModel = monaco.editor.createModel(modified_content || '', 'python', monaco.Uri.parse(`inmemory://model/modified/${modified_label}`));
        editor.setModel({ original: originalModel, modified: modifiedModel });
    } catch (e) { warn('Failed to set diff content', e); }
}
function set_read_only(read_only) { 
    if (editor) { try {
        if (isDiffEditorInstance(editor)) {
            const orig = editor.getOriginalEditor(); const mod = editor.getModifiedEditor();
            if (orig?.updateOptions) orig.updateOptions({ readOnly: read_only });
            if (mod?.updateOptions) mod.updateOptions({ readOnly: read_only });
        } else { if (editor.updateOptions) editor.updateOptions({ readOnly: read_only }); }
    } catch (e) { warn('Failed to set read-only', e); } }
}
function set_content(content, language, uri_string, callback_id) {
    if (!editor) return;
    try {
        isEditorModelReady = false;
        const currentModel = isDiffEditorInstance(editor) ? null : editor.getModel();
        if (currentModel) { disposeModel(currentModel); }
        if (isDiffEditorInstance(editor)) {
            const orig = editor.getOriginalEditor(); const mod = editor.getModifiedEditor();
            if (orig) disposeModel(orig.getModel());
            if (mod) disposeModel(mod.getModel());
        }
        disposeListener(contentChangeListener); contentChangeListener = null; disposeListener(modelSetListener); modelSetListener = null;
        const uri = uri_string ? monaco.Uri.parse(uri_string) : monaco.Uri.parse('inmemory://model/1');
        const newModel = monaco.editor.createModel(content || '', language || 'plaintext', uri);
        contentChangeListener = newModel.onDidChangeContent(() => { if (bridge) { try { bridge.on_content_changed(); } catch (e) { warn('bridge.on_content_changed failed', e); } } });
        modelSetListener = (() => { if (isDiffEditorInstance(editor)) { return null; } try { isEditorModelReady = true; } catch (e) { warn('modelSetListener failed', e); } return null; })();
        if (!isDiffEditorInstance(editor)) { editor.setModel(newModel); isEditorModelReady = true; }
        else { const originalModel = monaco.editor.createModel('', language || 'plaintext'); try { editor.setModel({ original: originalModel, modified: newModel }); } catch (e) { warn('diff editor setModel failed', e); const mod = editor.getModifiedEditor(); if (mod?.setModel) { mod.setModel(newModel); } } isEditorModelReady = true; }
        if (bridge) { try { bridge.on_model_ready(callback_id); } catch (e) { warn('bridge.on_model_ready failed', e); } }
    } catch (e) { err('Failed to set content', e); }
}
function add_extra_lib(content, uri) {
    if (monaco && content && uri) {
        try {



            monaco.editor.createModel(content, 'python', monaco.Uri.parse(uri));
            log('Successfully injected pf.pyi as an extra lib.');
        } catch(e) {
            warn('Failed to add extra library for pf script', e);
        }
    }
}
function apply_hunk(text_to_insert) { 
    const model = getActiveModel(); if (!editor || !model) return; 
    try {
        const selection = isDiffEditorInstance(editor) ? editor.getModifiedEditor().getSelection() : editor.getSelection(); 
        if (selection) {
            const op = { range: selection, text: text_to_insert || '', forceMoveMarkers: true }; 
            if (isDiffEditorInstance(editor)) {
                const modEd = editor.getModifiedEditor(); if (modEd?.executeEdits) modEd.executeEdits('forge-hunk-paste', [op]);
            } else { editor.executeEdits('forge-hunk-paste', [op]); }
        }
    } catch (e) { warn('Failed to apply hunk', e); }
}
function resolve_completions(callback_id, lsp_completions) {
    if (!pending_completions.has(callback_id)) return;
    const resolve = pending_completions.get(callback_id);
    if (!isEditorModelReady) { resolve({ suggestions: [] }); pending_completions.delete(callback_id); return; }
    const suggestions = (lsp_completions || []).map(item => {
        try {
            if (!item || !item.label) return null;
            const suggestion = { label: item.label, kind: lsp_kind_to_monaco_kind(item.kind || 1), insertText: item.insertText || item.label };
            if (item.detail && typeof item.detail === 'string') { suggestion.detail = item.detail; }
            if (item.documentation) { let docValue = (typeof item.documentation === 'string') ? item.documentation : (item.documentation?.value || ''); if (docValue) { suggestion.documentation = { value: docValue }; } }
            return suggestion;
        } catch (e) { warn('Completion item mapping failed', e); return null; }
    }).filter(Boolean);
    resolve({ suggestions }); pending_completions.delete(callback_id);
}
function resolve_hover(callback_id, lsp_hover) {
    if (!pending_hovers.has(callback_id)) return;
    const resolve = pending_hovers.get(callback_id);
    if (!lsp_hover || !lsp_hover.contents) { resolve(null); }
    else { const contents = Array.isArray(lsp_hover.contents) ? lsp_hover.contents : [lsp_hover.contents]; const monaco_hover_contents = contents.filter(Boolean).map(c => ({ value: (typeof c === 'string') ? c : (c?.value || '') })); resolve({ contents: monaco_hover_contents }); }
    pending_hovers.delete(callback_id);
}
function resolve_code_actions(callback_id, actions) { if (pending_code_actions.has(callback_id)) { pending_code_actions.get(callback_id)({ actions: actions || [], dispose: () => {} }); pending_code_actions.delete(callback_id); } }
function resolve_codelens(callback_id, lenses) { if (pending_codelens.has(callback_id)) { pending_codelens.get(callback_id)({ lenses: lenses || [], dispose: () => {} }); pending_codelens.delete(callback_id); } }
function set_semantic_tokens(data, callback_id) {
    if (semanticTokenProviderHandle) { try { semanticTokenProviderHandle.dispose(); } catch (e) { warn('semantic provider dispose failed', e); } semanticTokenProviderHandle = null; }
    const provider = {
        getLegend: () => ({ tokenTypes: ['class', 'parameter', 'function', 'method', 'decorator', 'property', 'namespace', 'variable', 'type', 'keyword', 'selfParameter', 'clsParameter'], tokenModifiers: ['definition', 'async', 'readonly', 'defaultLibrary'] }),
        provideDocumentSemanticTokens: (model, lastResultId, token) => {
            try {
                const tokenData = Array.isArray(data) ? data : [];
                const finalTokens = [];
                if (model.uri.toString().endsWith('.pfscript') && !isPyForgeSessionActive) {
                    let prevLine = 0; let prevChar = 0;
                    for (let i = 0; i < tokenData.length; i += 5) {
                        const deltaLine = tokenData[i]; const deltaChar = tokenData[i+1]; const len = tokenData[i+2]; const type = tokenData[i+3]; const mod = tokenData[i+4];
                        const line = prevLine + deltaLine; const char = deltaLine === 0 ? prevChar + deltaChar : deltaChar;
                        const tokenText = model.getValueInRange(new monaco.Range(line + 1, char + 1, line + 1, char + 1 + len));
                        if (tokenText === 'pf') {
                            finalTokens.push(deltaLine, deltaChar, len, 8, mod);
                        } else { finalTokens.push(deltaLine, deltaChar, len, type, mod); }
                        prevLine = line; prevChar = char;
                    }
                    return { data: new Uint32Array(finalTokens), resultId: `id-${Date.now()}` };
                }
                return { data: new Uint32Array(data), resultId: `id-${Date.now()}` };
            } catch (e) { warn('Failed to provide semantic tokens', e); return { data: new Uint32Array([]), resultId: `id-${Date.now()}` }; }
        },
        releaseDocumentSemanticTokens: (resultId) => {}
    };
    try { semanticTokenProviderHandle = monaco.languages.registerDocumentSemanticTokensProvider('python', provider); } catch (e) { warn('registerDocumentSemanticTokensProvider failed', e); }
    if (bridge) { try { bridge.on_semantic_tokens_applied(callback_id); } catch (e) { warn('bridge.on_semantic_tokens_applied failed', e); } }
}
function getText(callback_id) { if (editor && bridge) { try { const model = getActiveModel(); const value = model ? (model.getValue() || '') : ''; bridge.receive_text(callback_id, value); } catch (e) { warn('bridge.receive_text failed', e); } } }
function layout_editor() { if (editor) { try { if (isDiffEditorInstance(editor)) { const orig = editor.getOriginalEditor(); const mod = editor.getModifiedEditor(); if (orig?.layout) orig.layout(); if (mod?.layout) mod.layout(); } else if (editor.layout) { editor.layout(); } } catch (e) { warn('editor.layout failed', e); } } }
function set_diagnostics(markers) { const model = getActiveModel(); if (model) { try { monaco.editor.setModelMarkers(model, 'forge-diagnostics', markers || []); } catch (e) { warn('setModelMarkers failed', e); } } }
function jump_and_highlight(line, char) {
    if (!editor) return;
    try {
        const position = { lineNumber: line, column: char };
        if (isDiffEditorInstance(editor)) {
            const mod = editor.getModifiedEditor();
            if (mod?.setPosition) mod.setPosition(position);
            if (editor.revealLineInCenter) editor.revealLineInCenter(line);
            if (mod) { const model = mod.getModel(); if (model) { const range = { startLineNumber: line, startColumn: 1, endLineNumber: line, endColumn: model.getLineMaxColumn(line) }; mod.setSelection(range); } mod.focus(); }
        } else {
            editor.setPosition(position); editor.revealLineInCenter(line);
            const model = editor.getModel(); if (model) { const range = { startLineNumber: line, startColumn: 1, endLineNumber: line, endColumn: model.getLineMaxColumn(line) }; editor.setSelection(range); } editor.focus();
        }
    } catch (e) { warn('jump_and_highlight failed', e); }
}
function lsp_kind_to_monaco_kind(kind) {
    const map = monaco.languages.CompletionItemKind;
    switch (kind) {
        case 1: return map.Text; case 2: return map.Method; case 3: return map.Function; case 4: return map.Constructor; case 5: return map.Field; case 6: return map.Variable; case 7: return map.Class; case 8: return map.Interface; case 9: return map.Module; case 10: return map.Property; case 11: return map.Unit; case 12: return map.Value; case 13: return map.Enum; case 14: return map.Keyword; case 15: return map.Snippet; case 16: return map.Color; case 17: return map.File; case 18: return map.Reference; case 19: return map.Folder; case 20: return map.EnumMember; case 21: return map.Constant; case 22: return map.Struct; case 23: return map.Event; case 24: return map.Operator; case 25: return map.TypeParameter; default: return map.Text;
    }
}
function go_to_next_change() {
    if (!editor || !diffChanges || diffChanges.length === 0) return;
    currentDiffIndex++; if (currentDiffIndex >= diffChanges.length) currentDiffIndex = 0; const change = diffChanges[currentDiffIndex]; if (!change) return;
    try {
        const modifiedEditor = isDiffEditorInstance(editor) ? editor.getModifiedEditor() : editor; const targetLine = change.modifiedStartLineNumber || change.modifiedEndLineNumber || change.originalStartLineNumber;
        if (modifiedEditor && modifiedEditor.getModel && targetLine) { if (editor.revealLineInCenter) editor.revealLineInCenter(targetLine, monaco.editor.ScrollType.Smooth); const range = { startLineNumber: targetLine, startColumn: 1, endLineNumber: targetLine, endColumn: modifiedEditor.getModel().getLineMaxColumn(targetLine) }; if (modifiedEditor.setSelection) modifiedEditor.setSelection(range); if (modifiedEditor.focus) modifiedEditor.focus(); }
    } catch (e) { warn('go_to_next_change failed', e); }
}
function go_to_previous_change() {
    if (!editor || !diffChanges || diffChanges.length === 0) return;
    currentDiffIndex--; if (currentDiffIndex < 0) currentDiffIndex = diffChanges.length - 1; const change = diffChanges[currentDiffIndex]; if (!change) return;
    try {
        const modifiedEditor = isDiffEditorInstance(editor) ? editor.getModifiedEditor() : editor; const targetLine = change.modifiedStartLineNumber || change.modifiedEndLineNumber || change.originalStartLineNumber;
        if (modifiedEditor && modifiedEditor.getModel && targetLine) { if (editor.revealLineInCenter) editor.revealLineInCenter(targetLine, monaco.editor.ScrollType.Smooth); const range = { startLineNumber: targetLine, startColumn: 1, endLineNumber: targetLine, endColumn: modifiedEditor.getModel().getLineMaxColumn(targetLine) }; if (modifiedEditor.setSelection) modifiedEditor.setSelection(range); if (modifiedEditor.focus) modifiedEditor.focus(); }
    } catch (e) { warn('go_to_previous_change failed', e); }
}

window.forge = {
    initialize_editor, set_content, set_theme, set_diff_content, set_read_only, add_extra_lib, apply_hunk, resolve_completions,
    resolve_hover, resolve_code_actions, resolve_codelens, set_semantic_tokens, getText, layout_editor, set_diagnostics,
    jump_and_highlight, check_for_conflicts, accept_merge, enter_merge_mode, exit_merge_mode, go_to_next_change,
    go_to_previous_change, set_pyforge_session_active
};