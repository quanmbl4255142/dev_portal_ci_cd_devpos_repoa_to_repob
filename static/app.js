// Model counter for unique IDs
let modelCounter = 0;
let fieldCounters = {};

// Django field types
const FIELD_TYPES = [
    'CharField',
    'TextField',
    'IntegerField',
    'FloatField',
    'DecimalField',
    'BooleanField',
    'DateField',
    'DateTimeField',
    'EmailField',
    'URLField',
    'SlugField',
    'FileField',
    'ImageField',
    'JSONField'
];

// Initialize form
document.addEventListener('DOMContentLoaded', function() {
    // Add first model by default
    addModel();
});

// Handle form submission
document.getElementById('projectForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    // Show loading
    Swal.fire({
        title: 'Đang tạo project...',
        html: 'Vui lòng đợi trong giây lát',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    try {
        const config = collectFormData();
        
        // Validate
        if (!config.models || config.models.length === 0) {
            throw new Error('Phải có ít nhất 1 model');
        }
        
        // Call API
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Lỗi khi tạo project');
        }
        
        // Download file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${config.project_name}.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        // Show success
        Swal.fire({
            icon: 'success',
            title: 'Thành công!',
            html: `
                <p class="mb-4">Project <strong>${config.project_name}</strong> đã được tạo thành công!</p>
                <div class="text-left bg-gray-100 p-4 rounded">
                    <p class="font-semibold mb-2">Bước tiếp theo:</p>
                    <ol class="list-decimal list-inside space-y-1 text-sm">
                        <li>Giải nén file ${config.project_name}.zip</li>
                        <li>Cài đặt dependencies: <code>pip install -r requirements.txt</code></li>
                        <li>Chạy migrations: <code>python manage.py migrate</code></li>
                        <li>Chạy server: <code>python manage.py runserver</code></li>
                    </ol>
                </div>
            `,
            confirmButtonText: 'Tuyệt vời!'
        });
        
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Lỗi!',
            text: error.message
        });
    }
});

// Collect form data
function collectFormData() {
    const config = {
        project_name: document.getElementById('projectName').value.trim(),
        app_name: document.getElementById('appName').value.trim(),
        github_username: document.getElementById('githubUsername').value.trim() || null,
        git_repo_url: document.getElementById('gitRepoUrl').value.trim() || null,
        docker_registry: document.getElementById('dockerRegistry').value.trim() || 'ghcr.io',
        repo_b_url: document.getElementById('repoBUrl').value.trim() || null,
        enable_cors: document.getElementById('enableCors').checked,
        enable_cicd: document.getElementById('enableCicd').checked,
        models: []
    };
    
    // Collect models
    const modelCards = document.querySelectorAll('.model-card');
    modelCards.forEach(card => {
        const modelId = card.dataset.modelId;
        const modelName = document.getElementById(`modelName_${modelId}`).value.trim();
        const apiEndpoint = document.getElementById(`apiEndpoint_${modelId}`).value.trim();
        
        if (modelName && apiEndpoint) {
            const model = {
                name: modelName,
                api_endpoint: apiEndpoint,
                fields: []
            };
            
            // Collect fields
            const fieldRows = card.querySelectorAll('.field-row');
            fieldRows.forEach(row => {
                const fieldName = row.querySelector('.field-name').value.trim();
                const fieldType = row.querySelector('.field-type').value;
                
                if (fieldName && fieldType) {
                    const field = {
                        name: fieldName,
                        type: fieldType,
                        max_length: null,
                        decimal_places: null,
                        max_digits: null,
                        blank: row.querySelector('.field-blank')?.checked || false,
                        null: row.querySelector('.field-null')?.checked || false,
                        default: row.querySelector('.field-default')?.value.trim() || null
                    };
                    
                    // Add type-specific params
                    if (fieldType === 'CharField') {
                        const maxLength = row.querySelector('.field-max-length')?.value;
                        field.max_length = maxLength ? parseInt(maxLength) : 100;
                    } else if (fieldType === 'DecimalField') {
                        field.max_digits = parseInt(row.querySelector('.field-max-digits')?.value || 10);
                        field.decimal_places = parseInt(row.querySelector('.field-decimal-places')?.value || 2);
                    }
                    
                    model.fields.push(field);
                }
            });
            
            if (model.fields.length > 0) {
                config.models.push(model);
            }
        }
    });
    
    return config;
}

// Add new model
function addModel() {
    const modelId = modelCounter++;
    fieldCounters[modelId] = 0;
    
    const modelHtml = `
        <div class="model-card bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg p-6 shadow-md" data-model-id="${modelId}">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-xl font-bold text-gray-800 flex items-center">
                    <i class="fas fa-table text-purple-600 mr-2"></i>
                    Model #${modelId + 1}
                </h3>
                <button type="button" onclick="removeModel(${modelId})" 
                        class="text-red-500 hover:text-red-700 transition">
                    <i class="fas fa-trash"></i> Xóa
                </button>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">Tên Model</label>
                    <input type="text" id="modelName_${modelId}" required
                           placeholder="vd: Product, User, Post"
                           class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent">
                    <p class="text-xs text-gray-500 mt-1">Tên class model (PascalCase)</p>
                </div>
                
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">API Endpoint</label>
                    <input type="text" id="apiEndpoint_${modelId}" required
                           placeholder="vd: products, users, posts"
                           class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent">
                    <p class="text-xs text-gray-500 mt-1">URL path cho API (lowercase)</p>
                </div>
            </div>
            
            <div class="mb-4">
                <div class="flex items-center justify-between mb-3">
                    <label class="block text-sm font-semibold text-gray-700">Fields</label>
                    <button type="button" onclick="addField(${modelId})" 
                            class="px-4 py-1 bg-purple-600 hover:bg-purple-700 text-white text-sm rounded-lg transition">
                        <i class="fas fa-plus"></i> Thêm Field
                    </button>
                </div>
                
                <div id="fieldsContainer_${modelId}" class="space-y-3">
                    <!-- Fields will be added here -->
                </div>
            </div>
        </div>
    `;
    
    document.getElementById('modelsContainer').insertAdjacentHTML('beforeend', modelHtml);
    
    // Add first field
    addField(modelId);
}

// Remove model
function removeModel(modelId) {
    Swal.fire({
        title: 'Xác nhận xóa?',
        text: 'Bạn có chắc muốn xóa model này?',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Xóa',
        cancelButtonText: 'Hủy'
    }).then((result) => {
        if (result.isConfirmed) {
            const modelCard = document.querySelector(`[data-model-id="${modelId}"]`);
            modelCard.remove();
            delete fieldCounters[modelId];
        }
    });
}

// Add field to model
function addField(modelId) {
    const fieldId = fieldCounters[modelId]++;
    
    const fieldHtml = `
        <div class="field-row bg-white p-4 rounded-lg border border-gray-200" data-field-id="${fieldId}">
            <div class="grid grid-cols-1 md:grid-cols-12 gap-3 items-start">
                <div class="md:col-span-3">
                    <label class="block text-xs font-medium text-gray-600 mb-1">Tên Field</label>
                    <input type="text" class="field-name w-full px-3 py-2 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                           placeholder="vd: name, price">
                </div>
                
                <div class="md:col-span-3">
                    <label class="block text-xs font-medium text-gray-600 mb-1">Loại</label>
                    <select class="field-type field-type-select w-full px-3 py-2 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-purple-500 focus:border-transparent appearance-none"
                            onchange="handleFieldTypeChange(this)">
                        ${FIELD_TYPES.map(type => `<option value="${type}">${type}</option>`).join('')}
                    </select>
                </div>
                
                <div class="md:col-span-2 field-params">
                    <!-- Type-specific params will appear here -->
                </div>
                
                <div class="md:col-span-2">
                    <label class="block text-xs font-medium text-gray-600 mb-1">Options</label>
                    <div class="flex items-center space-x-2">
                        <label class="flex items-center cursor-pointer" title="Blank">
                            <input type="checkbox" class="field-blank w-4 h-4 text-purple-600 rounded">
                            <span class="ml-1 text-xs">Blank</span>
                        </label>
                        <label class="flex items-center cursor-pointer" title="Null">
                            <input type="checkbox" class="field-null w-4 h-4 text-purple-600 rounded">
                            <span class="ml-1 text-xs">Null</span>
                        </label>
                    </div>
                </div>
                
                <div class="md:col-span-1">
                    <label class="block text-xs font-medium text-gray-600 mb-1">&nbsp;</label>
                    <button type="button" onclick="removeField(${modelId}, ${fieldId})" 
                            class="text-red-500 hover:text-red-700 transition px-2 py-2">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById(`fieldsContainer_${modelId}`).insertAdjacentHTML('beforeend', fieldHtml);
}

// Remove field
function removeField(modelId, fieldId) {
    const fieldRow = document.querySelector(`[data-model-id="${modelId}"] [data-field-id="${fieldId}"]`);
    fieldRow.remove();
}

// Handle field type change
function handleFieldTypeChange(selectElement) {
    const fieldRow = selectElement.closest('.field-row');
    const paramsContainer = fieldRow.querySelector('.field-params');
    const fieldType = selectElement.value;
    
    let paramsHtml = '';
    
    if (fieldType === 'CharField') {
        paramsHtml = `
            <label class="block text-xs font-medium text-gray-600 mb-1">Max Length</label>
            <input type="number" class="field-max-length w-full px-3 py-2 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                   value="100" min="1">
        `;
    } else if (fieldType === 'DecimalField') {
        paramsHtml = `
            <label class="block text-xs font-medium text-gray-600 mb-1">Digits</label>
            <div class="flex space-x-1">
                <input type="number" class="field-max-digits w-1/2 px-2 py-2 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-purple-500"
                       value="10" min="1" placeholder="Max">
                <input type="number" class="field-decimal-places w-1/2 px-2 py-2 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-purple-500"
                       value="2" min="0" placeholder="Dec">
            </div>
        `;
    }
    
    paramsContainer.innerHTML = paramsHtml;
}

// Preview project
async function previewProject() {
    Swal.fire({
        title: 'Đang tạo preview...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    try {
        const config = collectFormData();
        
        // Validate
        if (!config.models || config.models.length === 0) {
            throw new Error('Phải có ít nhất 1 model');
        }
        
        const response = await fetch('/api/preview', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Lỗi khi preview');
        }
        
        const data = await response.json();
        
        // Show preview
        Swal.fire({
            title: 'Preview Project',
            html: `
                <div class="text-left">
                    <div class="mb-4">
                        <p class="font-semibold text-lg mb-2">📦 Tổng cộng: ${data.total_files} files</p>
                        <div class="bg-gray-100 p-3 rounded max-h-40 overflow-y-auto">
                            <ul class="text-sm space-y-1">
                                ${data.file_list.map(file => `<li><i class="fas fa-file text-gray-500"></i> ${file}</li>`).join('')}
                            </ul>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <p class="font-semibold mb-2">📄 models.py (Preview)</p>
                        <pre class="bg-gray-900 text-green-400 p-3 rounded text-xs overflow-x-auto max-h-40">${escapeHtml(data.preview['models.py'] || '')}</pre>
                    </div>
                    
                    <div class="mb-3">
                        <p class="font-semibold mb-2">📄 views.py (Preview)</p>
                        <pre class="bg-gray-900 text-green-400 p-3 rounded text-xs overflow-x-auto max-h-40">${escapeHtml(data.preview['views.py'] || '')}</pre>
                    </div>
                </div>
            `,
            width: '80%',
            confirmButtonText: 'OK',
            customClass: {
                popup: 'text-left'
            }
        });
        
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Lỗi!',
            text: error.message
        });
    }
}

// 🚀 Generate and Auto-Deploy
async function generateAndDeploy() {
    // Validate GitHub token
    const githubToken = document.getElementById('githubToken').value.trim();
    if (!githubToken) {
        Swal.fire({
            icon: 'warning',
            title: 'Thiếu GitHub Token',
            text: 'Bạn cần nhập GitHub Personal Access Token để auto-deploy!'
        });
        return;
    }
    
    const repoAName = document.getElementById('repoAName').value.trim();
    if (!repoAName) {
        Swal.fire({
            icon: 'warning',
            title: 'Thiếu Repository Name',
            text: 'Bạn cần nhập tên Repository_A!'
        });
        return;
    }
    
    // Show loading with steps
    Swal.fire({
        title: '🚀 Đang Auto-Deploy...',
        html: `
            <div class="text-left space-y-3">
                <div id="step-1" class="flex items-center space-x-2">
                    <i class="fas fa-spinner fa-spin text-blue-500"></i>
                    <span>Đang generate project files...</span>
                </div>
                <div id="step-2" class="flex items-center space-x-2 text-gray-400">
                    <i class="fas fa-circle text-xs"></i>
                    <span>Chờ push lên Repository_A...</span>
                </div>
                <div id="step-3" class="flex items-center space-x-2 text-gray-400">
                    <i class="fas fa-circle text-xs"></i>
                    <span>Chờ add GitHub secrets...</span>
                </div>
                <div id="step-4" class="flex items-center space-x-2 text-gray-400">
                    <i class="fas fa-circle text-xs"></i>
                    <span>Chờ GitHub Actions build image...</span>
                </div>
                <div id="step-5" class="flex items-center space-x-2 text-gray-400">
                    <i class="fas fa-circle text-xs"></i>
                    <span>Chờ generate K8s manifests...</span>
                </div>
                <div id="step-6" class="flex items-center space-x-2 text-gray-400">
                    <i class="fas fa-circle text-xs"></i>
                    <span>Chờ push lên Repository_B...</span>
                </div>
            </div>
        `,
        allowOutsideClick: false,
        showConfirmButton: false
    });
    
    try {
        const projectConfig = collectFormData();
        
        // Validate
        if (!projectConfig.models || projectConfig.models.length === 0) {
            throw new Error('Phải có ít nhất 1 model');
        }
        
        if (!projectConfig.github_username) {
            throw new Error('GitHub username là bắt buộc');
        }
        
        const deployConfig = {
            project_config: projectConfig,
            github_token: githubToken,
            repo_a_name: repoAName,
            repo_b_name: document.getElementById('repoBName').value.trim() || null,
            create_new_repo_a: document.getElementById('createNewRepoA').checked,
            repo_a_private: document.getElementById('repoAPrivate').checked,
            auto_push_repo_b: document.getElementById('autoPushRepoB').checked
        };
        
        // Call API
        const response = await fetch('/api/generate-and-deploy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(deployConfig)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail?.error || error.detail || 'Lỗi khi deploy');
        }
        
        const result = await response.json();
        
        // Update steps display
        updateStepStatus(result.steps);
        
        // Show success
        const summary = result.summary;
        Swal.fire({
            icon: 'success',
            title: '🎉 Deploy Thành Công!',
            html: `
                <div class="text-left">
                    <div class="mb-4 p-4 bg-green-50 rounded-lg">
                        <p class="font-semibold text-lg mb-2">✅ Hoàn tất tất cả bước!</p>
                    </div>
                    
                    <div class="space-y-3 mb-4">
                        <div class="p-3 bg-blue-50 rounded">
                            <p class="font-semibold text-sm mb-1">📦 Repository_A (Django Code):</p>
                            <a href="${summary.repository_a_url}" target="_blank" class="text-blue-600 hover:underline text-sm break-all">
                                ${summary.repository_a_url}
                            </a>
                        </div>
                        
                        ${summary.workflow_url ? `
                        <div class="p-3 bg-green-50 rounded">
                            <p class="font-semibold text-sm mb-1">🔄 GitHub Actions Workflow:</p>
                            <a href="${summary.workflow_url}" target="_blank" class="text-green-600 hover:underline text-sm break-all">
                                ${summary.workflow_url}
                            </a>
                            <p class="text-xs text-gray-600 mt-1">✅ Docker image đã được build và push lên GHCR</p>
                        </div>
                        ` : ''}
                        
                        ${summary.repository_b_url ? `
                        <div class="p-3 bg-purple-50 rounded">
                            <p class="font-semibold text-sm mb-1">🔧 Repository_B (K8s Manifests):</p>
                            <a href="${summary.repository_b_url}" target="_blank" class="text-purple-600 hover:underline text-sm break-all">
                                ${summary.repository_b_url}
                            </a>
                        </div>
                        ` : ''}
                    </div>
                    
                    <div class="bg-gray-100 p-4 rounded">
                        <p class="font-semibold mb-2 text-sm">🚀 Bước tiếp theo:</p>
                        <ul class="list-disc list-inside space-y-1 text-sm">
                            ${summary.next_steps.map(step => `<li>${step}</li>`).join('')}
                        </ul>
                        
                        ${summary.argocd_app ? `
                        <div class="mt-3 p-2 bg-yellow-50 rounded border border-yellow-200">
                            <p class="font-semibold text-xs mb-1">📋 Deploy với ArgoCD:</p>
                            <code class="text-xs bg-gray-800 text-green-400 p-2 rounded block overflow-x-auto">
                                ${summary.argocd_app}
                            </code>
                        </div>
                        ` : ''}
                    </div>
                </div>
            `,
            width: '800px',
            confirmButtonText: 'Tuyệt vời! 🎉'
        });
        
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Lỗi Deploy!',
            html: `
                <div class="text-left">
                    <p class="mb-2"><strong>Lỗi:</strong></p>
                    <pre class="bg-red-50 p-3 rounded text-sm overflow-x-auto">${error.message}</pre>
                    <p class="mt-3 text-sm text-gray-600">Vui lòng kiểm tra:</p>
                    <ul class="list-disc list-inside text-sm text-gray-600 mt-1">
                        <li>GitHub Token có đủ quyền (repo, workflow)?</li>
                        <li>Repository_B có tồn tại không?</li>
                        <li>Username và token có chính xác không?</li>
                    </ul>
                </div>
            `,
            width: '700px'
        });
    }
}

// Update step status display
function updateStepStatus(steps) {
    steps.forEach((step, index) => {
        const stepNum = index + 1;
        const stepElement = document.getElementById(`step-${stepNum}`);
        if (stepElement && step.status === 'success') {
            stepElement.innerHTML = `
                <i class="fas fa-check-circle text-green-500"></i>
                <span class="text-green-700">${getStepMessage(step.step)} ✓</span>
            `;
            stepElement.classList.remove('text-gray-400');
            
            // Activate next step
            const nextStep = document.getElementById(`step-${stepNum + 1}`);
            if (nextStep) {
                nextStep.classList.remove('text-gray-400');
                nextStep.innerHTML = nextStep.innerHTML.replace(
                    'fa-circle',
                    'fa-spinner fa-spin'
                ).replace('Chờ', 'Đang');
            }
        }
    });
}

// Get step display message
function getStepMessage(stepName) {
    const messages = {
        'generate_project': 'Generate project files',
        'push_to_repo_a': 'Push code lên Repository_A',
        'add_github_secrets': 'Add GitHub secrets',
        'wait_github_actions': 'Đợi GitHub Actions build Docker image',
        'generate_k8s_manifests': 'Generate K8s manifests',
        'push_to_repo_b': 'Push manifests lên Repository_B'
    };
    return messages[stepName] || stepName;
}

// Helper function
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

