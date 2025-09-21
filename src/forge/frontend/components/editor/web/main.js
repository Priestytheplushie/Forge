
require.config({ paths: { 'vs': 'vs' } });

let editor;
let bridge;
let diff_bridge;
let isEditorModelReady = false;
const pending_completions = new Map();
const pending_hovers = new Map();
const pending_conflict_checks = new Map();
let currentMergeDecorations = [];


function init() {
    console.log("[JS] Bridge is ready, initializing Monaco...");

    monaco.languages.registerCompletionItemProvider('python', {
        provideCompletionItems: (model, position) => {
            if (model.uri.scheme !== 'file' || !isEditorModelReady || !bridge) return { suggestions: [] };
            const uri = model.uri.toString();
            const callback_id = `completion-${Date.now()}-${Math.random()}`;
            return new Promise(resolve => {
                pending_completions.set(callback_id, resolve);
                bridge.request_completions(callback_id, uri, position.lineNumber, position.column);
            });
        }
    });

    monaco.languages.registerHoverProvider('python', {
        provideHover: (model, position) => {
            if (model.uri.scheme !== 'file' || !isEditorModelReady || !bridge) return null;
            const uri = model.uri.toString();
            const callback_id = `hover-${Date.now()}-${Math.random()}`;
            return new Promise(resolve => {
                pending_hovers.set(callback_id, resolve);
                bridge.request_hover(callback_id, uri, position.lineNumber, position.column);
            });
        }
    });

    monaco.languages.registerCodeLensProvider('*', {
        provideCodeLenses: function (model, token) {
            if (!model.isMergeConflict) return;
            const content = model.getValue();
            const conflictRegex = /(<<<<<<< HEAD)[\s\S]*?(=======)[\s\S]*?(>>>>>>> [\s\S]*?)/g;
            let match;
            const lenses = [];
            while ((match = conflictRegex.exec(content)) !== null) {
                const startLine = model.getPositionAt(match.index).lineNumber;
                const range = { startLineNumber: startLine, startColumn: 1, endLineNumber: startLine, endColumn: 1 };
                lenses.push(
                    { range, command: { title: "Accept Current", id: "merge.acceptCurrent", arguments: [range] } },
                    { range, command: { title: "Accept Incoming", id: "merge.acceptIncoming", arguments: [range] } },
                    { range, command: { title: "Accept Both", id: "merge.acceptBoth", arguments: [range] } },
                );
            }
            return { lenses, dispose: () => {} };
        }
    });

        monaco.editor.registerCommand('merge.acceptCurrent', (accessor, range) => { accept_merge('current', range); });
    monaco.editor.registerCommand('merge.acceptIncoming', (accessor, range) => { accept_merge('incoming', range); });
    monaco.editor.registerCommand('merge.acceptBoth', (accessor, range) => { accept_merge('both', range); });
    console.log("[JS] All LSP providers and merge commands registered successfully.");
}

require(['vs/editor/editor.main'], function () {
    console.log("[JS] Monaco loader has finished.");
    new QWebChannel(qt.webChannelTransport, function (channel) {
        console.log("[JS] QWebChannel has connected successfully.");
        bridge = channel.objects?.bridge;
        diff_bridge = channel.objects?.diff_bridge;

                if (bridge) {
            console.log("[JS] Standard editor bridge found. Signaling ready to Python.");
            bridge.on_web_channel_ready();
        } else if (diff_bridge) {
            console.log("[JS] Diff editor bridge found. Signaling ready to Python.");
            diff_bridge.on_web_channel_ready();
        } else {
            console.error("[JS] CRITICAL: No valid bridge object (bridge/diff_bridge) found.");
        }
    });
});

function initialize_editor(themeData, isDiffEditor = false) {
    if (!monaco) { return; }
    if (editor) { editor.dispose(); }
    if (themeData) { monaco.editor.defineTheme('forge-theme', themeData); monaco.editor.setTheme('forge-theme'); }

    const editorOptions = {
        'semanticHighlighting.enabled': true,
        readOnlyMessage: { value: '' } 
    };

    if (isDiffEditor) {
        editor = monaco.editor.createDiffEditor(document.getElementById('container'), {
            ...editorOptions,
            originalEditable: false,
            readOnly: true,
        });
        const addStageAction = (ed, isModified) => {
            ed.addAction({
                id: `forge-stage-lines-${isModified ? 'modified' : 'original'}`,
                label: 'Stage Selected Lines',
                contextMenuGroupId: '9_cutcopypaste',
                contextMenuOrder: 1.6,
                precondition: 'editorHasSelection',
                run: e => {
                    if (diff_bridge) {
                        const selection = e.getSelection();
                        const text = e.getModel().getValueInRange(selection);
                        const prefix = isModified ? '+' : '-';
                        const hunk = text.split('\n').map(line => prefix + line).join('\n');
                        diff_bridge.on_stage_lines(hunk);
                    }
                }
            });
        };
        addStageAction(editor.getOriginalEditor(), false);
        addStageAction(editor.getModifiedEditor(), true);
        if (diff_bridge) diff_bridge.js_loaded();
    } else {
        editor = monaco.editor.create(document.getElementById('container'), {
            ...editorOptions,
            language: 'plaintext',
            quickSuggestions: true,
            hover: { enabled: true }, 
            codeLens: true,
        });

                editor.addAction({
            id: 'forge-stage-lines-normal',
            label: 'Stage Selected Lines',
            contextMenuGroupId: '9_cutcopypaste',
            contextMenuOrder: 1.6,
            precondition: 'editorHasSelection',
            run: ed => { if (bridge) { const selection = ed.getSelection(); const text = ed.getModel().getValueInRange(selection); const hunk = text.split('\n').map(line => '+' + line).join('\n'); bridge.on_stage_lines(hunk); } }
        });

        editor.addAction({
            id: 'forge-apply-staged-changes',
            label: 'Apply Staged Changes',
            contextMenuGroupId: '9_cutcopypaste',
            contextMenuOrder: 1.7,
            run: ed => { if(bridge) bridge.on_apply_staged_changes(); }
        });

        editor.onDidChangeCursorPosition(e => { if (bridge) bridge.on_cursor_position_changed(e.position.lineNumber, e.position.column); });

        if(bridge){
            bridge.undo_requested.connect(() => editor.trigger('keyboard', 'undo', null));
            bridge.redo_requested.connect(() => editor.trigger('keyboard', 'redo', null));
            bridge.cut_requested.connect(() => editor.trigger('keyboard', 'cut', null));
            bridge.copy_requested.connect(() => editor.trigger('keyboard', 'copy', null));
            bridge.paste_requested.connect(() => editor.trigger('keyboard', 'paste', null));
        }

                if (bridge) {
            init();
            bridge.js_loaded();
        }
    }
}

function enter_merge_mode() {
    if (!editor || !editor.getModel()) return;
    editor.getModel().isMergeConflict = true; 
    update_merge_decorations();
    editor.getModel().pushEditOperations([], [{ range: new monaco.Range(1, 1, 1, 1), text: "" }], () => null);
}

function exit_merge_mode() {
    if (!editor || !editor.getModel()) return;
    editor.getModel().isMergeConflict = false; 
    currentMergeDecorations = editor.deltaDecorations(currentMergeDecorations, []);
    editor.getModel().pushEditOperations([], [{ range: new monaco.Range(1, 1, 1, 1), text: "" }], () => null);
}

function update_merge_decorations() {
    if (!editor) return;
    const model = editor.getModel();
    if (!model) return;
    const content = model.getValue();
    const conflictRegex = /(<<<<<<< HEAD\r?\n)([\s\S]*?)(=======)(\r?\n[\s\S]*?)(>>>>>>> [\s\S]*?(\r?\n)?)/g;
    let match;
    const newDecorations = [];
    while ((match = conflictRegex.exec(content)) !== null) {
        const startPos = model.getPositionAt(match.index);
        newDecorations.push({
            range: new monaco.Range(startPos.lineNumber + 1, 1, startPos.lineNumber + 1 + match[2].split('\n').length - 1, 1),
            options: { isWholeLine: true, className: 'merge-current-content' }
        });
        const incomingStartLine = model.getPositionAt(match.index + match[1].length + match[2].length + match[3].length).lineNumber;
        newDecorations.push({
            range: new monaco.Range(incomingStartLine + 1, 1, incomingStartLine + match[4].split('\n').length - 1, 1),
            options: { isWholeLine: true, className: 'merge-incoming-content' }
        });
    }
    currentMergeDecorations = editor.deltaDecorations(currentMergeDecorations, newDecorations);
}

function accept_merge(type, conflictRange) {
    if (!editor) return;
    const model = editor.getModel();
    if (!model || !conflictRange) return;

    const content = model.getValue();
    const conflictRegex = /(<<<<<<< HEAD\r?\n)([\s\S]*?)(=======)(\r?\n[\s\S]*?)(>>>>>>> [\s\S]*?(\r?\n)?)/g;
    let match;
    let targetMatch = null;

    while ((match = conflictRegex.exec(content)) !== null) {
        const startPos = model.getPositionAt(match.index);
        const endPos = model.getPositionAt(match.index + match[0].length);
        if (conflictRange.startLineNumber >= startPos.lineNumber && conflictRange.startLineNumber <= endPos.lineNumber) {
            targetMatch = match;
            break;
        }
    }

    if (!targetMatch) return;

    const currentContent = targetMatch[2].trim();
    const incomingContent = targetMatch[4].substring(targetMatch[4].indexOf('\n') + 1).trim();
    let resolvedText;
    if (type === 'current') {
        resolvedText = currentContent;
    } else if (type === 'incoming') {
        resolvedText = incomingContent;
    } else if (type === 'both') {
        resolvedText = currentContent + '\n' + incomingContent;
    } else {
        return;
    }

    const startPos = model.getPositionAt(targetMatch.index);
    const endPos = model.getPositionAt(targetMatch.index + targetMatch[0].length);
    const range = new monaco.Range(startPos.lineNumber, startPos.column, endPos.lineNumber, endPos.column);
    const op = { range: range, text: resolvedText };
    model.pushEditOperations([], [op], () => null);

    update_merge_decorations();
}

function check_for_conflicts(callback_id) {
    if (!bridge) { console.warn("check_for_conflicts called before bridge was ready."); return; }
    const model = editor ? editor.getModel() : null;
    if (!model) {
        bridge.receive_conflict_check_result(callback_id, false);
        return;
    }
    const hasConflicts = model.getValue().includes('<<<<<<<');
    bridge.receive_conflict_check_result(callback_id, hasConflicts);
}

function set_theme(themeData) { if (monaco && themeData) { monaco.editor.defineTheme('forge-theme', themeData); monaco.editor.setTheme('forge-theme'); } }
function set_diff_content(original_content, modified_content, original_label, modified_label) { if (!editor || typeof editor.setModel !== 'function') return; const originalModel = monaco.editor.createModel(original_content, 'python'); const modifiedModel = monaco.editor.createModel(modified_content, 'python'); editor.setModel({ original: originalModel, modified: modifiedModel }); }
function set_read_only(read_only) { if (editor) editor.updateOptions({ readOnly: read_only }); }
function set_content(content, language, uri_string, callback_id) { if (!editor) return; isEditorModelReady = false; let currentModel = editor.getModel(); if (currentModel) { if(currentModel.original) currentModel.original.dispose(); if(currentModel.modified) currentModel.modified.dispose(); if(!currentModel.original && !currentModel.modified) currentModel.dispose(); } let contentChangeListener; let modelSetListener; if (contentChangeListener) contentChangeListener.dispose(); if (modelSetListener) modelSetListener.dispose(); const newModel = monaco.editor.createModel(content, language, monaco.Uri.parse(uri_string)); contentChangeListener = newModel.onDidChangeContent(() => { if (bridge) bridge.on_content_changed(); }); modelSetListener = editor.onDidChangeModel(() => { isEditorModelReady = true; if (modelSetListener) modelSetListener.dispose(); }); editor.setModel(newModel); if (bridge) bridge.on_model_ready(callback_id); }
function apply_hunk(text_to_insert) { if (!editor) return; const selection = editor.getSelection(); const op = { range: selection, text: text_to_insert, forceMoveMarkers: true }; editor.executeEdits('forge-hunk-paste', [op]); }
function resolve_completions(callback_id, lsp_completions) { if (!pending_completions.has(callback_id)) return; const resolve = pending_completions.get(callback_id); if (!isEditorModelReady) { resolve({ suggestions: [] }); pending_completions.delete(callback_id); return; } const suggestions = (lsp_completions || []).map(item => { try { if (!item || !item.label) return null; const suggestion = { label: item.label, kind: lsp_kind_to_monaco_kind(item.kind || 1), insertText: item.insertText || item.label }; if (item.detail && typeof item.detail === 'string') suggestion.detail = item.detail; if (item.documentation) { let docValue = (typeof item.documentation === 'string') ? item.documentation : item.documentation?.value || ''; if (docValue) suggestion.documentation = { value: docValue }; } return suggestion; } catch (e) { console.error(`Completion item error: ${e}. Item: ${JSON.stringify(item)}`); return null; } }).filter(Boolean); resolve({ suggestions }); pending_completions.delete(callback_id); }
function resolve_hover(callback_id, lsp_hover) { if (!pending_hovers.has(callback_id)) return; const resolve = pending_hovers.get(callback_id); if (!lsp_hover || !lsp_hover.contents) { resolve(null); } else { const contents = Array.isArray(lsp_hover.contents) ? lsp_hover.contents : [lsp_hover.contents]; const monaco_hover_contents = contents.filter(Boolean).map(c => ({ value: (typeof c === 'string') ? c : c?.value || '' })); resolve({ contents: monaco_hover_contents }); } pending_hovers.delete(callback_id); }
function set_semantic_tokens(data, callback_id) { let semanticTokenProviderHandle; if (semanticTokenProviderHandle) semanticTokenProviderHandle.dispose(); const newProvider = { getLegend: () => ({ tokenTypes: ['class','parameter','function','method','decorator','property','namespace','variable','type','keyword','selfParameter','clsParameter'], tokenModifiers: ['definition','async','readonly','defaultLibrary'] }), provideDocumentSemanticTokens: () => ({ data: new Uint32Array(Array.isArray(data) ? data : []), resultId: `id-${Date.now()}` }), releaseDocumentSemanticTokens: () => {} }; semanticTokenProviderHandle = monaco.languages.registerDocumentSemanticTokensProvider('python', newProvider); if (bridge) bridge.on_semantic_tokens_applied(callback_id); }
function getText(callback_id) { if (editor && bridge) bridge.receive_text(callback_id, editor.getValue() || ''); }
function layout_editor() { if (editor) editor.layout(); }
function set_diagnostics(markers) { if (editor && editor.getModel()) { monaco.editor.setModelMarkers(editor.getModel(), 'forge-diagnostics', markers || []); } }
function jump_and_highlight(line, char) { if (editor) { const position = { lineNumber: line, column: char }; editor.setPosition(position); editor.revealLineInCenter(line); const model = editor.getModel(); if (model) { const range = { startLineNumber: line, startColumn: 1, endLineNumber: line, endColumn: model.getLineMaxColumn(line) }; editor.setSelection(range); } editor.focus(); } }
function lsp_kind_to_monaco_kind(kind) { const map = monaco.languages.CompletionItemKind; switch (kind) { case 1: return map.Text; case 2: return map.Method; case 3: return map.Function; case 4: return map.Constructor; case 5: return map.Field; case 6: return map.Variable; case 7: return map.Class; case 8: return map.Interface; case 9: return map.Module; case 10: return map.Property; case 11: return map.Unit; case 12: return map.Value; case 13: return map.Enum; case 14: return map.Keyword; case 15: return map.Snippet; case 16: return map.Color; case 17: return map.File; case 18: return map.Reference; case 19: return map.Folder; case 20: return map.EnumMember; case 21: return map.Constant; case 22: return map.Struct; case 23: return map.Event; case 24: return map.Operator; case 25: return map.TypeParameter; default: return map.Text; } }