// AI Tool Risk Calculator - Real-time risk assessment calculations
class RiskCalculator {
    constructor() {
        this.riskThresholds = {
            data_sensitivity: {
                'phi': 0.9,
                'pii': 0.7,
                'confidential': 0.6,
                'internal': 0.4,
                'public': 0.1
            },
            deployment_model: {
                'saas': 0.7,
                'hybrid': 0.5,
                'self_hosted': 0.2,
                'on_premise': 0.1
            },
            user_types_risk: {
                'admins': 0.9,
                'developers': 0.7,
                'data_scientists': 0.7,
                'operators': 0.6,
                'analysts': 0.5,
                'non_technical': 0.3
            },
            data_types_risk: {
                'phi': 1.0,
                'pii': 0.8,
                'source_code': 0.6,
                'logs': 0.4,
                'metadata': 0.3,
                'prompts': 0.4,
                'credentials': 0.9,
                'financial': 0.8
            },
            auth_model_risk: {
                'no_auth': 1.0,
                'basic_auth': 0.8,
                'api_key': 0.6,
                'oauth': 0.4,
                'saml_sso': 0.2,
                'enterprise_sso': 0.1
            },
            data_storage_risk: {
                'vendor_cloud': 0.8,
                'shared_storage': 0.7,
                'dedicated_storage': 0.4,
                'local_only': 0.2,
                'no_storage': 0.1
            }
        };

        this.pressureMultipliers = {
            timeline_pressure: {
                'immediate': 1.3,
                'one_week': 1.2,
                'one_month': 1.1,
                'three_months': 1.0,
                'six_months': 0.9
            },
            executive_pressure: {
                'critical': 1.4,
                'high': 1.2,
                'medium': 1.0,
                'low': 0.9,
                'none': 0.8
            }
        };
    }

    calculateRisk(formData) {
        const riskFactors = {
            data_sensitivity: this.calculateDataSensitivityRisk(formData),
            access_scope: this.calculateAccessScopeRisk(formData),
            deployment: this.calculateDeploymentRisk(formData),
            persistence: this.calculatePersistenceRisk(formData),
            authentication: this.calculateAuthenticationRisk(formData),
            pressure: this.calculatePressureRisk(formData)
        };

        const overallRisk = this.calculateOverallRisk(riskFactors);
        const recommendation = this.generateRecommendation(overallRisk, riskFactors, formData);

        return {
            risk_factors: riskFactors,
            overall_risk: overallRisk,
            recommendation: recommendation,
            risk_score: this.calculateNumericRiskScore(riskFactors)
        };
    }

    calculateDataSensitivityRisk(formData) {
        const dataSensitivity = formData.data_sensitivity || 'internal';
        const dataTypes = formData.data_types || [];
        
        // Base risk from sensitivity level
        let baseRisk = this.riskThresholds.data_sensitivity[dataSensitivity] || 0.5;
        
        // Amplify risk based on specific data types
        let dataTypeRisk = 0;
        dataTypes.forEach(dataType => {
            const typeRisk = this.riskThresholds.data_types_risk[dataType] || 0.3;
            dataTypeRisk = Math.max(dataTypeRisk, typeRisk);
        });

        // Combine risks (weighted average)
        const combinedRisk = (baseRisk * 0.6) + (dataTypeRisk * 0.4);
        
        return {
            level: this.scoreToLevel(combinedRisk),
            score: combinedRisk,
            justification: this.generateDataSensitivityJustification(dataSensitivity, dataTypes)
        };
    }

    calculateAccessScopeRisk(formData) {
        const intendedUsers = formData.intended_users || [];
        
        if (intendedUsers.length === 0) {
            return {
                level: 'moderate',
                score: 0.5,
                justification: 'User scope not specified'
            };
        }

        // Find highest risk user type
        let maxRisk = 0;
        let riskiestUser = '';
        
        intendedUsers.forEach(userType => {
            const userRisk = this.riskThresholds.user_types_risk[userType] || 0.3;
            if (userRisk > maxRisk) {
                maxRisk = userRisk;
                riskiestUser = userType;
            }
        });

        // Additional risk for broad access
        const scopeMultiplier = intendedUsers.length > 2 ? 1.1 : 1.0;
        const finalRisk = Math.min(maxRisk * scopeMultiplier, 1.0);

        return {
            level: this.scoreToLevel(finalRisk),
            score: finalRisk,
            justification: this.generateAccessScopeJustification(intendedUsers, riskiestUser)
        };
    }

    calculateDeploymentRisk(formData) {
        const deploymentModel = formData.deployment_model || 'saas';
        const baseRisk = this.riskThresholds.deployment_model[deploymentModel] || 0.5;
        
        // Adjust for integration points
        const integrationPoints = formData.integration_points || [];
        const integrationRisk = integrationPoints.length * 0.05; // Small increase per integration
        
        const finalRisk = Math.min(baseRisk + integrationRisk, 1.0);

        return {
            level: this.scoreToLevel(finalRisk),
            score: finalRisk,
            justification: this.generateDeploymentJustification(deploymentModel, integrationPoints)
        };
    }

    calculatePersistenceRisk(formData) {
        const dataStorage = formData.data_storage || 'vendor_cloud';
        const dataRetention = formData.data_retention || 'unknown';
        
        let baseRisk = this.riskThresholds.data_storage_risk[dataStorage] || 0.5;
        
        // Adjust for retention policy
        const retentionMultiplier = {
            'no_retention': 0.7,
            'session_only': 0.8,
            'thirty_days': 1.0,
            'one_year': 1.2,
            'indefinite': 1.4,
            'unknown': 1.3
        };
        
        const finalRisk = Math.min(baseRisk * (retentionMultiplier[dataRetention] || 1.0), 1.0);

        return {
            level: this.scoreToLevel(finalRisk),
            score: finalRisk,
            justification: this.generatePersistenceJustification(dataStorage, dataRetention)
        };
    }

    calculateAuthenticationRisk(formData) {
        const authModel = formData.auth_model || 'unknown';
        const authzModel = formData.authz_model || 'unknown';
        
        let authRisk = this.riskThresholds.auth_model_risk[authModel] || 0.6;
        
        // Adjust for authorization model
        const authzAdjustment = {
            'rbac': 0.9,
            'abac': 0.8,
            'basic': 1.0,
            'none': 1.3,
            'unknown': 1.2
        };
        
        const finalRisk = Math.min(authRisk * (authzAdjustment[authzModel] || 1.0), 1.0);

        return {
            level: this.scoreToLevel(finalRisk),
            score: finalRisk,
            justification: this.generateAuthenticationJustification(authModel, authzModel)
        };
    }

    calculatePressureRisk(formData) {
        const timelinePressure = formData.timeline_pressure || 'three_months';
        const executivePressure = formData.executive_pressure || 'medium';
        
        const timelineMultiplier = this.pressureMultipliers.timeline_pressure[timelinePressure] || 1.0;
        const executiveMultiplier = this.pressureMultipliers.executive_pressure[executivePressure] || 1.0;
        
        // Base pressure risk
        const baseRisk = 0.3;
        const combinedMultiplier = (timelineMultiplier + executiveMultiplier) / 2;
        const finalRisk = Math.min(baseRisk * combinedMultiplier, 1.0);

        return {
            level: this.scoreToLevel(finalRisk),
            score: finalRisk,
            justification: this.generatePressureJustification(timelinePressure, executivePressure)
        };
    }

    calculateOverallRisk(riskFactors) {
        // Weighted risk calculation
        const weights = {
            data_sensitivity: 0.25,
            access_scope: 0.20,
            deployment: 0.20,
            persistence: 0.15,
            authentication: 0.15,
            pressure: 0.05
        };

        let weightedScore = 0;
        Object.keys(weights).forEach(factor => {
            if (riskFactors[factor]) {
                weightedScore += riskFactors[factor].score * weights[factor];
            }
        });

        return this.scoreToLevel(weightedScore);
    }

    calculateNumericRiskScore(riskFactors) {
        const weights = {
            data_sensitivity: 0.25,
            access_scope: 0.20,
            deployment: 0.20,
            persistence: 0.15,
            authentication: 0.15,
            pressure: 0.05
        };

        let score = 0;
        Object.keys(weights).forEach(factor => {
            if (riskFactors[factor]) {
                score += riskFactors[factor].score * weights[factor];
            }
        });

        return Math.round(score * 100);
    }

    generateRecommendation(overallRisk, riskFactors, formData) {
        // Business pressure considerations
        const timelinePressure = formData.timeline_pressure;
        const executivePressure = formData.executive_pressure;
        const highPressure = timelinePressure === 'immediate' || executivePressure === 'critical';

        // High-risk scenarios
        if (overallRisk === 'high') {
            return highPressure ? 'conditional_go' : 'no_go';
        }

        // Moderate risk scenarios
        if (overallRisk === 'moderate') {
            // Check for specific high-risk factors
            const hasPhiAccess = riskFactors.data_sensitivity?.score >= 0.8;
            const hasBroadAccess = riskFactors.access_scope?.score >= 0.7;
            const hasWeakAuth = riskFactors.authentication?.score >= 0.7;

            if (hasPhiAccess && (hasBroadAccess || hasWeakAuth)) {
                return 'conditional_go';
            }
            
            return 'conditional_go';
        }

        // Low risk scenarios
        return 'go';
    }

    scoreToLevel(score) {
        if (score >= 0.7) return 'high';
        if (score >= 0.4) return 'moderate';
        return 'low';
    }

    // Justification generators
    generateDataSensitivityJustification(sensitivity, dataTypes) {
        const sensitivityText = sensitivity.replace('_', ' ').toUpperCase();
        const typesText = dataTypes.length > 0 ? 
            `including ${dataTypes.slice(0, 2).join(', ')}${dataTypes.length > 2 ? '...' : ''}` :
            'with unspecified types';
        
        return `Processes ${sensitivityText} data ${typesText}`;
    }

    generateAccessScopeJustification(users, riskiestUser) {
        const userText = users.map(u => u.replace('_', ' ')).join(', ');
        const scopeText = users.length > 2 ? 'broad user base' : 'limited user scope';
        
        return `Accessible by ${userText} (${scopeText})`;
    }

    generateDeploymentJustification(deployment, integrations) {
        const deployText = deployment.replace('_', ' ');
        const integText = integrations.length > 0 ? 
            ` with ${integrations.length} integration${integrations.length > 1 ? 's' : ''}` :
            '';
        
        return `${deployText} deployment${integText}`;
    }

    generatePersistenceJustification(storage, retention) {
        const storageText = storage.replace('_', ' ');
        const retentionText = retention.replace('_', ' ');
        
        return `${storageText} storage with ${retentionText} retention`;
    }

    generateAuthenticationJustification(auth, authz) {
        const authText = auth.replace('_', ' ');
        const authzText = authz !== 'unknown' ? ` and ${authz.replace('_', ' ')} authorization` : '';
        
        return `Uses ${authText} authentication${authzText}`;
    }

    generatePressureJustification(timeline, executive) {
        const timelineText = timeline.replace('_', ' ');
        const executiveText = executive.replace('_', ' ');
        
        return `${timelineText} timeline with ${executiveText} executive pressure`;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RiskCalculator;
}
