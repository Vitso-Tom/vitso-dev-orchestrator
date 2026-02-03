/**
 * Risk Calculator v2 - Updated for slim form
 * Handles Unknown defaults gracefully
 */

class RiskCalculator {
    constructor() {
        this.weights = {
            data_exposure: 0.25,      // Increased - most important
            identity_surface: 0.10,   // Decreased - less user input
            vendor_maturity: 0.20,    
            ai_model_risk: 0.25,      // Increased - AI-specific risks matter
            integration_risk: 0.10,   
            operational_risk: 0.10    
        };

        this.thresholds = {
            low: 35,
            moderate: 65
        };

        this.onRiskUpdate = null;
        this.init();
    }

    init() {
        const form = document.getElementById('assessment-form');
        if (form) {
            form.addEventListener('input', () => this.calculate());
            form.addEventListener('change', () => this.calculate());
        }
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

        let totalScore = 0;
        let totalWeight = 0;

        for (const [category, score] of Object.entries(scores)) {
            const weight = this.weights[category];
            totalScore += score * weight;
            totalWeight += weight;
        }

        const overallScore = totalWeight > 0 ? totalScore / totalWeight : 0;
        const riskLevel = this.getRiskLevel(overallScore);

        this.updateDisplay(overallScore, riskLevel, scores);

        if (this.onRiskUpdate) {
            this.onRiskUpdate({ overallScore, riskLevel, scores });
        }

        return { overallScore, riskLevel, scores };
    }

    calculateDataExposure() {
        let score = 0;

        // Data types selected (0-50 points) - most important factor
        const dataTypes = this.getCheckedValues('data_types');
        if (dataTypes.includes('phi')) score += 50;      // PHI is critical
        else if (dataTypes.includes('pii')) score += 35;
        else if (dataTypes.includes('credentials')) score += 30;
        else if (dataTypes.includes('financial')) score += 25;
        else if (dataTypes.includes('code')) score += 15;
        else if (dataTypes.includes('internal')) score += 5;
        else score += 20; // Nothing selected = unknown exposure

        // Deployment model (0-25 points)
        const deployment = this.getFormValue('deployment_model', 'unknown');
        const deploymentScores = {
            'on_prem': 5,
            'hybrid': 15,
            'saas': 25,
            'unknown': 20
        };
        score += deploymentScores[deployment] || 20;

        // Retention needs (0-25 points)
        const retention = this.getFormValue('data_retention', 'unknown');
        const retentionScores = {
            'none': 0,
            'session_only': 5,
            '30_days': 10,
            '90_days': 15,
            '1_year_plus': 20,
            'unknown': 15
        };
        score += retentionScores[retention] || 15;

        return Math.min(100, score);
    }

    calculateIdentitySurface() {
        let score = 20; // Base score

        // Intended users scope (0-30 points)
        const users = this.getCheckedValues('intended_users');
        if (users.includes('all_users')) score += 30;
        else if (users.includes('clinical')) score += 25; // Clinical = PHI risk
        else if (users.length > 2) score += 20;
        else if (users.length > 0) score += 10;
        // No users selected = score stays at base

        return Math.min(100, score);
    }

    calculateVendorMaturity() {
        // Start at moderate risk, reduce with positive signals
        let riskScore = 50;

        // SOC 2 (reduces risk by 20)
        const soc2 = this.getFormValue('vendor_soc2', '');
        if (soc2 === 'true') riskScore -= 20;
        else if (soc2 === 'false') riskScore += 15;
        // Unknown = no change

        // HIPAA BAA (reduces risk by 15)
        const baa = this.getFormValue('vendor_hipaa_baa', '');
        if (baa === 'true') riskScore -= 15;
        else if (baa === 'false') riskScore += 10;
        // Unknown = no change

        // Subprocessors disclosed (reduces risk by 10)
        const subprocessors = this.getFormValue('subprocessors_disclosed', '');
        if (subprocessors === 'true') riskScore -= 10;
        else if (subprocessors === 'false') riskScore += 15;
        // Unknown = no change

        return Math.max(0, Math.min(100, riskScore));
    }

    calculateAIModelRisk() {
        let score = 0;

        // Training on inputs (0-35 points)
        const training = this.getFormValue('training_on_inputs', 'unknown');
        const trainingScores = {
            'no': 0,
            'opt_out_available': 15,
            'yes': 35,
            'unknown': 25
        };
        score += trainingScores[training] || 25;

        // Model provider (0-20 points)
        const provider = this.getFormValue('model_provider', 'unknown');
        const providerScores = {
            'self_hosted': 5,
            'proprietary': 10,
            'azure': 10,
            'aws': 10,
            'anthropic': 12,
            'openai': 15,
            'google': 15,
            'multiple': 18,  // Multiple = more subprocessors
            'other': 18,
            'unknown': 20
        };
        score += providerScores[provider] || 20;

        // Agent capabilities (0-15 points)
        const agents = this.getFormValue('agent_capabilities', '');
        if (agents === 'true') score += 15;
        else if (agents === '') score += 8; // Unknown
        // No = 0

        // MCP support (0-10 points)
        const mcp = this.getFormValue('mcp_support', '');
        if (mcp === 'true') score += 10;
        else if (mcp === '') score += 5; // Unknown

        // RAG enabled (0-10 points)
        const rag = this.getFormValue('rag_enabled', '');
        if (rag === 'true') score += 10;
        else if (rag === '') score += 5; // Unknown

        return Math.min(100, score);
    }

    calculateIntegrationRisk() {
        let score = 0;

        // Deployment model (0-30 points)
        const deployment = this.getFormValue('deployment_model', 'unknown');
        const deploymentScores = {
            'on_prem': 10,
            'hybrid': 20,
            'saas': 30,
            'unknown': 25
        };
        score += deploymentScores[deployment] || 25;

        // MCP expands integration surface
        const mcp = this.getFormValue('mcp_support', '');
        if (mcp === 'true') score += 15;

        // RAG expands integration surface
        const rag = this.getFormValue('rag_enabled', '');
        if (rag === 'true') score += 10;

        return Math.min(100, score);
    }

    calculateOperationalRisk() {
        let score = 20; // Base operational risk

        // Timeline pressure (0-20 points)
        const timeline = this.getFormValue('timeline_pressure', 'normal');
        const timelineScores = {
            'flexible': 0,
            'normal': 5,
            'urgent': 20
        };
        score += timelineScores[timeline] || 5;

        // Model provider lock-in risk
        const provider = this.getFormValue('model_provider', 'unknown');
        if (provider === 'proprietary') score += 15;
        else if (provider === 'unknown') score += 10;

        return Math.min(100, score);
    }

    getRiskLevel(score) {
        if (score < this.thresholds.low) return 'low';
        if (score < this.thresholds.moderate) return 'moderate';
        return 'high';
    }

    updateDisplay(overallScore, riskLevel, categoryScores) {
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
