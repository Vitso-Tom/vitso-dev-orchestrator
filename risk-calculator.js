/**
 * Risk Calculator - Real-time risk preview
 * Mirrors backend risk_engine.py scoring logic
 */

class RiskCalculator {
    constructor() {
        this.weights = {
            data_exposure: 0.20,
            identity_surface: 0.15,
            vendor_maturity: 0.20,
            ai_model_risk: 0.20,
            integration_risk: 0.10,
            operational_risk: 0.15
        };
        
        this.thresholds = {
            low: 35,
            moderate: 65
        };
        
        this.onRiskUpdate = null;
        this.init();
    }
    
    init() {
        // Bind to form changes
        const form = document.getElementById('assessment-form');
        if (form) {
            form.addEventListener('input', () => this.calculate());
            form.addEventListener('change', () => this.calculate());
        }
        
        // Initial calculation
        setTimeout(() => this.calculate(), 500);
    }
    
    getFormValue(name, defaultValue = '') {
        const element = document.querySelector(`[name="${name}"]`);
        if (!element) return defaultValue;
        
        if (element.type === 'checkbox') {
            return element.checked;
        } else if (element.type === 'radio') {
            const checked = document.querySelector(`[name="${name}"]:checked`);
            return checked ? checked.value : defaultValue;
        }
        return element.value || defaultValue;
    }
    
    getCheckedValues(name) {
        const elements = document.querySelectorAll(`[name="${name}"]:checked`);
        return Array.from(elements).map(el => el.value);
    }
    
    calculate() {
        const scores = {
            data_exposure: this.calculateDataExposure(),
            identity_surface: this.calculateIdentitySurface(),
            vendor_maturity: this.calculateVendorMaturity(),
            ai_model_risk: this.calculateAIModelRisk(),
            integration_risk: this.calculateIntegrationRisk(),
            operational_risk: this.calculateOperationalRisk()
        };
        
        // Calculate weighted overall score
        let totalScore = 0;
        let totalWeight = 0;
        
        for (const [category, score] of Object.entries(scores)) {
            const weight = this.weights[category];
            totalScore += score * weight;
            totalWeight += weight;
        }
        
        const overallScore = totalWeight > 0 ? totalScore / totalWeight : 0;
        const riskLevel = this.getRiskLevel(overallScore);
        
        // Update UI
        this.updateDisplay(overallScore, riskLevel, scores);
        
        // Callback if set
        if (this.onRiskUpdate) {
            this.onRiskUpdate({ overallScore, riskLevel, scores });
        }
        
        return { overallScore, riskLevel, scores };
    }
    
    calculateDataExposure() {
        let score = 0;
        
        // Data sensitivity (0-40 points)
        const sensitivity = this.getFormValue('data_sensitivity', 'unknown');
        const sensitivityScores = {
            'phi': 40,
            'pii': 30,
            'confidential': 20,
            'internal': 10,
            'public': 0,
            'unknown': 25
        };
        score += sensitivityScores[sensitivity] || 25;
        
        // Data residency (0-25 points)
        const residency = this.getFormValue('data_residency', 'unknown');
        const residencyScores = {
            'us_only': 5,
            'eu': 10,
            'global': 20,
            'unknown': 25
        };
        score += residencyScores[residency] || 25;
        
        // Subprocessors (0-15 points)
        const subprocessors = this.getFormValue('data_subprocessors', '');
        if (subprocessors === 'true') score += 10;
        else if (subprocessors === 'false') score += 0;
        else score += 15;
        
        // Retention (0-20 points)
        const retention = this.getFormValue('data_retention', 'unknown');
        const retentionScores = {
            'none': 0,
            'session_only': 5,
            '30_days': 8,
            '90_days': 12,
            '1_year_plus': 18,
            'indefinite': 20,
            'unknown': 15
        };
        score += retentionScores[retention] || 15;
        
        return Math.min(100, score);
    }
    
    calculateIdentitySurface() {
        let score = 0;
        
        // Intended users scope (0-30 points)
        const users = this.getCheckedValues('intended_users');
        if (users.includes('all_users')) score += 30;
        else if (users.length > 3) score += 25;
        else if (users.length > 1) score += 15;
        else if (users.length === 1) score += 5;
        else score += 20; // unknown
        
        // Auth model (0-35 points)
        const authModel = this.getFormValue('auth_model', 'unknown');
        const authScores = {
            'sso': 5,
            'oauth': 10,
            'saml': 10,
            'api_key': 20,
            'username_password': 25,
            'unknown': 30
        };
        score += authScores[authModel] || 30;
        
        // Authz model (0-35 points)
        const authzModel = this.getFormValue('authz_model', 'unknown');
        const authzScores = {
            'rbac': 5,
            'abac': 5,
            'basic': 20,
            'none': 35,
            'unknown': 30
        };
        score += authzScores[authzModel] || 30;
        
        return Math.min(100, score);
    }
    
    calculateVendorMaturity() {
        // Higher points = more mature = LOWER risk
        // We invert at the end
        let maturityPoints = 0;
        
        // SOC 2 (0-30 points)
        const soc2 = this.getFormValue('vendor_soc2', '');
        if (soc2 === 'true') maturityPoints += 30;
        
        // HIPAA BAA (0-20 points)
        const baa = this.getFormValue('vendor_hipaa_baa', '');
        if (baa === 'true') maturityPoints += 20;
        
        // Security contact (0-10 points)
        const secContact = this.getFormValue('vendor_security_contact', '');
        if (secContact === 'true' || secContact.length > 0) maturityPoints += 10;
        
        // Company size (0-15 points)
        const size = this.getFormValue('vendor_employee_count', 'unknown');
        const sizePoints = {
            '1000+': 15,
            '201-1000': 12,
            '51-200': 8,
            '11-50': 4,
            '1-10': 0,
            'unknown': 0
        };
        maturityPoints += sizePoints[size] || 0;
        
        // Funding stage (0-15 points)
        const funding = this.getFormValue('vendor_funding_stage', 'unknown');
        const fundingPoints = {
            'public': 15,
            'growth': 12,
            'series_b': 8,
            'series_a': 5,
            'seed': 2,
            'bootstrap': 0,
            'unknown': 0
        };
        maturityPoints += fundingPoints[funding] || 0;
        
        // Invert: max 90 points possible, so risk = 100 - (points * 100/90)
        const riskScore = 100 - (maturityPoints * 100 / 90);
        return Math.max(0, Math.min(100, riskScore));
    }
    
    calculateAIModelRisk() {
        let score = 0;
        
        // Training on inputs (0-40 points)
        const training = this.getFormValue('training_on_inputs', 'unknown');
        const trainingScores = {
            'no': 0,
            'opt_out_available': 15,
            'yes': 40,
            'unknown': 35
        };
        score += trainingScores[training] || 35;
        
        // Prompt logging (0-25 points)
        const logging = this.getFormValue('prompt_logging', 'unknown');
        const loggingScores = {
            'no': 0,
            'configurable': 10,
            'yes': 25,
            'unknown': 20
        };
        score += loggingScores[logging] || 20;
        
        // Version pinning (0-15 points) - having it reduces risk
        const pinning = this.getFormValue('model_version_pinning', 'false');
        if (pinning !== 'true') score += 15;
        
        // Agent capabilities (0-10 points)
        const agents = this.getFormValue('agent_capabilities', 'false');
        if (agents === 'true') score += 10;
        
        // Plugin ecosystem (0-5 points)
        const plugins = this.getFormValue('plugin_ecosystem', 'false');
        if (plugins === 'true') score += 5;
        
        // MCP support (0-5 points)
        const mcp = this.getFormValue('mcp_support', 'false');
        if (mcp === 'true') score += 5;
        
        return Math.min(100, score);
    }
    
    calculateIntegrationRisk() {
        let score = 0;
        
        // Deployment model (0-30 points)
        const deployment = this.getFormValue('deployment_model', 'unknown');
        const deploymentScores = {
            'on_prem': 5,
            'self_hosted': 5,
            'hybrid': 15,
            'saas': 25,
            'unknown': 30
        };
        score += deploymentScores[deployment] || 30;
        
        // API access - more integration = more risk (0-15 points)
        const api = this.getFormValue('api_access', 'false');
        if (api === 'true') score += 10;
        
        // SSO support - reduces risk (0-20 points penalty if missing)
        const sso = this.getFormValue('sso_support', 'false');
        if (sso !== 'true') score += 20;
        
        // SCIM support - reduces risk (0-15 points penalty if missing)
        const scim = this.getFormValue('scim_support', 'false');
        if (scim !== 'true') score += 15;
        
        return Math.min(100, score);
    }
    
    calculateOperationalRisk() {
        let score = 0;
        
        // Data export capability - reduces lock-in risk
        const dataExport = this.getFormValue('data_export_capability', 'false');
        if (dataExport !== 'true') score += 25;
        
        // Vendor lock-in base score
        score += 20;
        
        // Model provider risk
        const provider = this.getFormValue('model_provider', 'unknown');
        const providerScores = {
            'openai': 15,
            'anthropic': 15,
            'google': 15,
            'aws': 10,
            'azure': 10,
            'self_hosted': 5,
            'other': 20,
            'unknown': 25
        };
        score += providerScores[provider] || 25;
        
        // Timeline pressure
        const timeline = this.getFormValue('timeline_pressure', 'normal');
        const timelineScores = {
            'normal': 0,
            'urgent': 10,
            'immediate': 20
        };
        score += timelineScores[timeline] || 0;
        
        return Math.min(100, score);
    }
    
    getRiskLevel(score) {
        if (score < this.thresholds.low) return 'low';
        if (score < this.thresholds.moderate) return 'moderate';
        return 'high';
    }
    
    updateDisplay(overallScore, riskLevel, categoryScores) {
        // Update overall score
        const scoreElement = document.getElementById('risk-score');
        const labelElement = document.getElementById('risk-label');
        const levelElement = document.getElementById('risk-level-display');
        
        if (scoreElement) {
            scoreElement.textContent = Math.round(overallScore);
        }
        
        if (labelElement) {
            labelElement.textContent = riskLevel.toUpperCase();
        }
        
        if (levelElement) {
            levelElement.className = 'risk-level ' + riskLevel;
        }
        
        // Update category scores
        const categoryMap = {
            'data_exposure': 'Data Exposure',
            'identity_surface': 'Identity Surface',
            'vendor_maturity': 'Vendor Maturity',
            'ai_model_risk': 'AI Model Risk',
            'integration_risk': 'Integration Risk',
            'operational_risk': 'Operational Risk'
        };
        
        for (const [key, score] of Object.entries(categoryScores)) {
            const factor = document.querySelector(`.factor[data-factor="${key}"] .score`);
            if (factor) {
                factor.textContent = Math.round(score);
                factor.className = 'score ' + this.getRiskLevel(score);
            }
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.riskCalculator = new RiskCalculator();
});
