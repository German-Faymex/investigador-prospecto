/* ================================================
   Investigador de Prospectos - Application JS
   ================================================ */

// --- Toast Notifications ---
function showToast(message, type) {
    type = type || 'success';
    var container = document.getElementById('toast-container');
    if (!container) return;

    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(function() {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 3000);
}

// --- Step Indicator ---
function updateStepIndicator(step) {
    for (var i = 1; i <= 3; i++) {
        var stepEl = document.getElementById('step-' + i);
        if (!stepEl) continue;

        var circle = stepEl.querySelector('.step-circle');
        var label = stepEl.querySelector('.step-label');

        if (i <= step) {
            stepEl.style.opacity = '1';
            if (circle) {
                circle.classList.remove('bg-gray-300', 'text-gray-600');
                circle.classList.add('bg-faymex-red', 'text-white');
            }
            if (label) {
                label.classList.remove('text-gray-500');
                label.classList.add('text-faymex-red');
            }
        } else {
            stepEl.style.opacity = '0.4';
            if (circle) {
                circle.classList.remove('bg-faymex-red', 'text-white');
                circle.classList.add('bg-gray-300', 'text-gray-600');
            }
            if (label) {
                label.classList.remove('text-faymex-red');
                label.classList.add('text-gray-500');
            }
        }
    }

    // Connectors
    var conn12 = document.getElementById('connector-1-2');
    var conn23 = document.getElementById('connector-2-3');
    if (conn12) {
        conn12.style.backgroundColor = step >= 2 ? '#D82A34' : '#d1d5db';
    }
    if (conn23) {
        conn23.style.backgroundColor = step >= 3 ? '#D82A34' : '#d1d5db';
    }
}

// --- Quill Editor ---
var quillInstance = null;

function initQuillEditor(containerId, content) {
    var container = document.getElementById(containerId);
    if (!container) return;

    quillInstance = new Quill('#' + containerId, {
        theme: 'snow',
        modules: {
            toolbar: [
                ['bold', 'italic', 'underline'],
                [{ 'list': 'bullet' }],
                ['link'],
                ['clean']
            ]
        },
        placeholder: 'Escribe el email aqui...'
    });

    if (content) {
        quillInstance.root.innerHTML = content;
    }

    // Update word count on text change
    quillInstance.on('text-change', function() {
        var text = quillInstance.getText().trim();
        var count = getWordCount(text);
        updateWordCount(count);
        validateEmail();
    });

    // Initial counts
    var initialText = quillInstance.getText().trim();
    updateWordCount(getWordCount(initialText));
    validateEmail();
}

function getWordCount(text) {
    if (!text || !text.trim()) return 0;
    return text.trim().split(/\s+/).length;
}

function updateWordCount(count) {
    var el = document.getElementById('word-count');
    if (el) {
        el.textContent = 'Palabras: ' + count;
    }
}

// --- Subject Counter ---
function updateSubjectCounter(input) {
    var counter = document.getElementById('subject-counter');
    if (!counter) return;

    var len = input.value.length;
    counter.textContent = len + '/40';

    if (len > 40) {
        counter.style.color = '#dc2626';
        counter.style.fontWeight = '600';
    } else {
        counter.style.color = '#9ca3af';
        counter.style.fontWeight = '400';
    }

    validateEmail();
}

// --- Email Validation ---
function validateEmail() {
    var el = document.getElementById('email-validity');
    if (!el) return;

    var subject = document.getElementById('email-subject');
    var subjectLen = subject ? subject.value.length : 0;
    var wordCount = quillInstance ? getWordCount(quillInstance.getText().trim()) : 0;

    var hasSubject = subjectLen > 0;
    var subjectOk = subjectLen <= 40;
    var bodyOk = wordCount >= 20;

    if (hasSubject && subjectOk && bodyOk) {
        el.innerHTML = '<span style="color:#16a34a">&#10003;</span> <span style="color:#16a34a">Email valido</span>';
    } else {
        var issues = [];
        if (!hasSubject) issues.push('falta asunto');
        if (!subjectOk) issues.push('asunto muy largo');
        if (!bodyOk) issues.push('cuerpo muy corto');
        el.innerHTML = '<span style="color:#ca8a04">&#9888;</span> <span style="color:#ca8a04">' + issues.join(', ') + '</span>';
    }
}

// --- Copy to Clipboard ---
function copyEmailToClipboard() {
    var subject = document.getElementById('email-subject');
    var subjectText = subject ? subject.value : '';

    var bodyText = '';
    if (quillInstance) {
        bodyText = quillInstance.getText().trim();
    } else {
        var plainTextEl = document.getElementById('email-plain-text');
        if (plainTextEl) bodyText = plainTextEl.value;
    }

    var fullText = 'Asunto: ' + subjectText + '\n\n' + bodyText;

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(fullText).then(function() {
            showToast('Email copiado al portapapeles', 'success');
        }).catch(function() {
            fallbackCopy(fullText);
        });
    } else {
        fallbackCopy(fullText);
    }
}

function fallbackCopy(text) {
    var textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand('copy');
        showToast('Email copiado al portapapeles', 'success');
    } catch (e) {
        showToast('No se pudo copiar', 'error');
    }
    document.body.removeChild(textarea);
}

// --- Reset Page ---
function resetPage() {
    // Clear form fields
    var form = document.getElementById('research-form');
    if (form) form.reset();

    // Empty results area
    var results = document.getElementById('research-results');
    if (results) results.innerHTML = '';

    // Reset step indicator to step 1
    updateStepIndicator(1);

    // Hide reset button
    var resetBtn = document.getElementById('reset-btn');
    if (resetBtn) {
        resetBtn.classList.add('hidden');
        resetBtn.classList.remove('flex');
    }

    // Scroll to top and focus first field
    window.scrollTo({ top: 0, behavior: 'smooth' });
    setTimeout(function() {
        var firstInput = form ? form.querySelector('input[name="name"]') : null;
        if (firstInput) firstInput.focus();
    }, 300);
}

// --- Stop Research ---
var activeXhr = null;

function stopResearch() {
    if (activeXhr) {
        activeXhr.abort();
        activeXhr = null;
    }
    // Also abort any active HTMX request on the form
    var form = document.getElementById('research-form');
    if (form) {
        htmx.trigger(form, 'htmx:abort');
    }
    var stopBtn = document.getElementById('stop-btn');
    var submitBtn = document.getElementById('submit-btn');
    if (stopBtn) stopBtn.classList.add('hidden');
    if (submitBtn) submitBtn.disabled = false;

    // Hide loading spinner
    var spinner = document.getElementById('loading-spinner');
    if (spinner) spinner.classList.remove('htmx-request');

    showToast('Investigacion detenida', 'warning');
}

// --- HTMX Event Handlers ---
document.addEventListener('htmx:beforeRequest', function(event) {
    // Show stop button when research starts
    if (event.detail.elt && event.detail.elt.id === 'research-form') {
        var stopBtn = document.getElementById('stop-btn');
        if (stopBtn) {
            stopBtn.classList.remove('hidden');
            stopBtn.classList.add('flex');
        }
        activeXhr = event.detail.xhr;
    }
});

document.addEventListener('htmx:afterSwap', function(event) {
    // Hide stop button and scroll to results
    var stopBtn = document.getElementById('stop-btn');
    if (stopBtn) {
        stopBtn.classList.add('hidden');
        stopBtn.classList.remove('flex');
    }
    activeXhr = null;

    // Show reset button when results arrive
    var resetBtn = document.getElementById('reset-btn');
    if (resetBtn && event.detail.target && event.detail.target.id === 'research-results') {
        resetBtn.classList.remove('hidden');
        resetBtn.classList.add('flex');
    }

    if (event.detail.target) {
        setTimeout(function() {
            event.detail.target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }
});

document.addEventListener('htmx:responseError', function(event) {
    var stopBtn = document.getElementById('stop-btn');
    if (stopBtn) {
        stopBtn.classList.add('hidden');
        stopBtn.classList.remove('flex');
    }
    activeXhr = null;
    var status = event.detail.xhr ? event.detail.xhr.status : 'unknown';
    showToast('Error del servidor (HTTP ' + status + '). Intenta nuevamente.', 'error');
});

document.addEventListener('htmx:sendError', function() {
    var stopBtn = document.getElementById('stop-btn');
    if (stopBtn) {
        stopBtn.classList.add('hidden');
        stopBtn.classList.remove('flex');
    }
    activeXhr = null;
    showToast('No se pudo conectar al servidor.', 'error');
});

document.addEventListener('htmx:timeout', function() {
    var stopBtn = document.getElementById('stop-btn');
    if (stopBtn) {
        stopBtn.classList.add('hidden');
        stopBtn.classList.remove('flex');
    }
    activeXhr = null;
    showToast('La solicitud tardo demasiado (>2 min). Intenta nuevamente.', 'warning');
});

document.addEventListener('htmx:beforeSwap', function(event) {
    // If server returned error status, show message and prevent empty swap
    var xhr = event.detail.xhr;
    if (xhr && xhr.status >= 400) {
        event.detail.shouldSwap = false;
        showToast('Error del servidor (HTTP ' + xhr.status + '). Intenta nuevamente.', 'error');
    }
});
