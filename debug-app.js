// AI Tool Onboarding Simulator - Main Application JavaScript
class ToolEvaluationApp {
    constructor() {
        this.form = document.getElementById('evaluationForm');
        this.riskPreview = document.getElementById('riskPreview');
        this.previewRisk = document.getElementById('previewRisk');
        this.riskCalculator = new RiskCalculator();
        
        this.initializeEventListeners();
        this.updateRiskPreview();
    }

    initializeEventListeners() {
        // Form field change listeners for real-time risk calculation
        const riskFields = [
            'data_sensitivity', 'deployment_model', 'data_storage', 
            'data_retention', 'auth_model', 'authz_model',
            'timeline_pressure', 'executive_pressure'
        ];

        riskFields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) {
                field.addEventListener('change', () => this.updateRiskPreview());
            }
        });

        // Checkbox group listeners
        const checkboxGroups = ['intended_users', 'data_types', 'model_interactions', 'integration_points'];
        checkboxGroups.forEach(groupName => {
            const checkboxes = document.querySelectorAll(`input[name="${groupName}"]`);
            checkboxes.forEach(checkbox => {
                checkbox.addEventListener('change', () => this.updateRiskPreview());
            });
        });

        // Form submission
        if (this.form) {
            this.form.addEventListener('submit', (e) => this.handleFormSubmission(e));
        }

        // Form validation on input
        this.setupFormValidation();

        // Dynamic field dependencies
        this.setupFieldDependencies();
    }

    updateRiskPreview() {
        const formData = this.collectFormData();
        const riskAssessment = this.riskCalculator.calculateRisk(formData);
        
        this.displayRiskPreview(riskAssessment);
    }

    collectFormData() {
        const formData = {};
        
        // Single value fields
        const singleFields = [
            'tool_name', 'vendor', 'use_cases', 'data_sensitivity',
            'auth_model', 'authz_model', 'data_storage', 'data_retention',
            'deployment_model', 'timeline_pressure', 'executive_pressure'
        ];

        singleFields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) {
                formData[fieldId] = field.value || '';
            }
        });

        // Multi-value fields (checkboxes)
        const multiFields = ['intended_users', 'data_types', 'model_interactions', 'integration_points'];
        multiFields.forEach(fieldName => {
            const checkboxes = document.querySelectorAll(`input[name="${fieldName}"]:checked`);
            formData[fieldName] = Array.from(checkboxes).map(cb => cb.value);
        });

        return formData;
    }

    displayRiskPreview(assessment) {
        if (!this.riskPreview) return;

        // Update overall risk display
        const overallRiskElement = document.getElementById('overallRisk');
        if (overallRiskElement) {
            overallRiskElement.textContent = assessment.overall_risk.toUpperCase();
            overallRiskElement.className = `risk-level risk-${assessment.overall_risk}`;
        }

        // Update individual risk factors
        this.updateRiskFactor('dataSensitivityRisk', assessment.risk_factors.data_sensitivity);
        this.updateRiskFactor('accessScopeRisk', assessment.risk_factors.access_scope);
        this.updateRiskFactor('deploymentRisk', assessment.risk_factors.deployment);

        // Update preliminary recommendation
        const recommendationElement = document.getElementById('preliminaryRecommendation');
        if (recommendationElement) {
            recommendationElement.textContent = assessment.recommendation.replace('_', ' ').toUpperCase();
            recommendationElement.className = `recommendation recommendation-${assessment.recommendation}`;
        }

        // Show/hide risk preview panel
        if (this.previewRisk) {
            const hasSignificantRisk = assessment.overall_risk !== 'low' || 
                                    assessment.recommendation !== 'go';
            this.previewRisk.style.display = hasSignificantRisk ? 'block' : 'none';
        }
    }

    updateRiskFactor(elementId, riskData) {
        const element = document.getElementById(elementId);
        if (element && riskData) {
            element.innerHTML = `
                <span class="risk-level risk-${riskData.level}">${riskData.level.toUpperCase()}</span>
                <small class="risk-justification">${riskData.justification}</small>
            `;
        }
    }

    setupFormValidation() {
        // Required field validation
        const requiredFields = ['tool_name', 'vendor', 'use_cases'];
        requiredFields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) {
                field.addEventListener('blur', () => this.validateField(field));
                field.addEventListener('input', () => this.clearFieldError(field));
            }
        });

        // Checkbox group validation
        this.validateCheckboxGroups();
    }

    validateField(field) {
        const isValid = field.value.trim() !== '';
        this.setFieldValidation(field, isValid, isValid ? '' : 'This field is required');
        return isValid;
    }

    validateCheckboxGroups() {
        const checkboxGroups = [
            { name: 'intended_users', label: 'Intended Users' },
            { name: 'data_types', label: 'Data Types' }
        ];

        checkboxGroups.forEach(group => {
            const checkboxes = document.querySelectorAll(`input[name="${group.name}"]`);
            checkboxes.forEach(checkbox => {
                checkbox.addEventListener('change', () => {
                    const checkedBoxes = document.querySelectorAll(`input[name="${group.name}"]:checked`);
                    const isValid = checkedBoxes.length > 0;
                    const container = checkbox.closest('.checkbox-group');
                    
                    if (container) {
                        this.setGroupValidation(container, isValid, 
                            isValid ? '' : `Please select at least one ${group.label.toLowerCase()}`);
                    }
                });
            });
        });
    }

    setFieldValidation(field, isValid, message) {
        const container = field.closest('.form-group');
        if (!container) return;

        // Remove existing error
        const existingError = container.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }

        // Update field styling
        field.classList.toggle('field-invalid', !isValid);
        field.classList.toggle('field-valid', isValid);

        // Add error message if invalid
        if (!isValid && message) {
            const errorElement = document.createElement('div');
            errorElement.className = 'field-error';
            errorElement.textContent = message;
            container.appendChild(errorElement);
        }
    }

    setGroupValidation(container, isValid, message) {
        // Remove existing error
        const existingError = container.querySelector('.group-error');
        if (existingError) {
            existingError.remove();
        }

        // Update container styling
        container.classList.toggle('group-invalid', !isValid);

        // Add error message if invalid
        if (!isValid && message) {
            const errorElement = document.createElement('div');
            errorElement.className = 'group-error';
            errorElement.textContent = message;
            container.appendChild(errorElement);
        }
    }

    clearFieldError(field) {
        field.classList.remove('field-invalid');
        const container = field.closest('.form-group');
        if (container) {
            const existingError = container.querySelector('.field-error');
            if (existingError) {
                existingError.remove();
            }
        }
    }

    setupFieldDependencies() {
        // Show/hide additional fields based on selections
        const deploymentField = document.getElementById('deployment_model');
        if (deploymentField) {
            deploymentField.addEventListener('change', () => {
                this.handleDeploymentChange(deploymentField.value);
            });
        }

        const dataStorageField = document.getElementById('data_storage');
        if (dataStorageField) {
            dataStorageField.addEventListener('change', () => {
                this.handleDataStorageChange(dataStorageField.value);
            });
        }
    }

    handleDeploymentChange(deploymentType) {
        // Could show/hide additional fields based on deployment type
        // For now, just update risk preview
        this.updateRiskPreview();
    }

    handleDataStorageChange(storageType) {
        // Could show/hide retention options based on storage type
        this.updateRiskPreview();
    }

    validateForm() {
        let isValid = true;

        // Validate required text fields
        const requiredFields = ['tool_name', 'vendor', 'use_cases'];
        requiredFields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field && !this.validateField(field)) {
                isValid = false;
            }
        });

        // Validate required checkbox groups
        const requiredGroups = ['intended_users', 'data_types'];
        requiredGroups.forEach(groupName => {
            const checkedBoxes = document.querySelectorAll(`input[name="${groupName}"]:checked`);
            const container = document.querySelector(`input[name="${groupName}"]`)?.closest('.checkbox-group');
            
            if (checkedBoxes.length === 0) {
                isValid = false;
                if (container) {
                    this.setGroupValidation(container, false, `Please select at least one ${groupName.replace('_', ' ')}`);
                }
            }
        });

        return isValid;
    }

    handleFormSubmission(event) {
        if (!this.validateForm()) {
            event.preventDefault();
            this.showValidationSummary();
            return false;
        }

        // Show loading state
        this.showLoadingState();
        return true;
    }

    showValidationSummary() {
        // Scroll to first error
        const firstError = document.querySelector('.field-invalid, .group-invalid');
        if (firstError) {
            firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        // Show temporary validation message
        this.showTemporaryMessage('Please correct the highlighted fields before submitting.', 'error');
    }

    showLoadingState() {
        const submitButton = this.form.querySelector('button[type="submit"]');
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = 'Analyzing...';
            submitButton.classList.add('button-loading');
        }
    }

    showTemporaryMessage(message, type = 'info') {
        // Remove existing message
        const existingMessage = document.querySelector('.temp-message');
        if (existingMessage) {
            existingMessage.remove();
        }

        // Create new message
        const messageElement = document.createElement('div');
        messageElement.className = `temp-message temp-message-${type}`;
        messageElement.textContent = message;

        // Insert at top of form
        this.form.insertBefore(messageElement, this.form.firstChild);

        // Auto-remove after delay
        setTimeout(() => {
            if (messageElement.parentNode) {
                messageElement.remove();
            }
        }, 5000);
    }
}

// Utility functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.toolEvaluationApp = new ToolEvaluationApp();
});

// Report page functionality
if (document.querySelector('.report-container')) {
    document.addEventListener('DOMContentLoaded', () => {
        // Print functionality
        const printButtons = document.querySelectorAll('.print-btn, .exec-print-btn');
        printButtons.forEach(button => {
            button.addEventListener('click', () => {
                window.print();
            });
        });

        // Collapsible sections in reports
        const collapsibleSections = document.querySelectorAll('.collapsible-section');
        collapsibleSections.forEach(section => {
            const header = section.querySelector('.section-header');
            if (header) {
                header.addEventListener('click', () => {
                    section.classList.toggle('collapsed');
                });
            }
        });

        // Risk level indicators animation
        const riskIndicators = document.querySelectorAll('.risk-level');
        riskIndicators.forEach(indicator => {
            indicator.style.opacity = '0';
            indicator.style.transform = 'scale(0.8)';
            
            setTimeout(() => {
                indicator.style.transition = 'all 0.3s ease';
                indicator.style.opacity = '1';
                indicator.style.transform = 'scale(1)';
            }, 100);
        });
    });
}
