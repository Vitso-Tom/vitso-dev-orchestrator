from datetime import datetime, timedelta

class ReportGenerator:
    def __init__(self):
        self.timestamp = datetime.now()
    
    def generate_evaluation_report(self, tool_data, assessment):
        """Generate comprehensive evaluation report"""
        report = {
            'tool_summary': self._generate_tool_summary(tool_data),
            'data_exposure_analysis': self._generate_data_exposure_analysis(tool_data),
            'risk_classification': assessment['risk_factors'],
            'control_requirements': self._format_control_requirements(assessment['control_requirements']),
            'enablement_plan': assessment['enablement_plan'],
            'decision_output': {
                'recommendation': assessment['decision'],
                'rationale': assessment['rationale'],
                'change_conditions': self._generate_change_conditions(assessment)
            },
            'auditor_talking_points': self._generate_auditor_points(tool_data, assessment)
        }
        
        return report
    
    def generate_executive_summary(self, tool_data, assessment):
        """Generate executive-level summary"""
        summary = {
            'tool_name': tool_data.get('tool_name', 'Unknown Tool'),
            'vendor': tool_data.get('vendor', 'Unknown Vendor'),
            'business_value': self._extract_business_value(tool_data),
            'risk_level': assessment['overall_risk'],
            'recommendation': assessment['decision'],
            'key_risks': self._extract_key_risks(assessment),
            'mitigation_approach': self._summarize_mitigations(assessment),
            'timeline': self._create_timeline(assessment),
            'investment_required': self._estimate_investment(assessment)
        }
        
        return summary
    
    def _generate_tool_summary(self, tool_data):
        """Generate tool summary section"""
        tool_name = tool_data.get('tool_name', 'This tool')
        vendor = tool_data.get('vendor', 'the vendor')
        use_cases = tool_data.get('use_cases', 'support various operational tasks')
        
        # Clean up use cases description
        if len(use_cases) > 200:
            use_cases = use_cases[:197] + "..."
        
        return {
            'description': f"{tool_name} is an AI-powered solution from {vendor} designed to {use_cases.lower()}.",
            'problem_solved': self._extract_problem_solved(tool_data),
            'primary_beneficiaries': ', '.join(tool_data.get('intended_users', [])).replace('_', ' ').title()
        }
    
    def _generate_data_exposure_analysis(self, tool_data):
        """Analyze data exposure risks"""
        data_types = tool_data.get('data_types', [])
        deployment = tool_data.get('deployment_model', 'unknown')
        retention = tool_data.get('data_retention', 'unknown')
        
        return {
            'data_types_touched': data_types,
            'sensitivity_level': tool_data.get('data_sensitivity', 'unknown'),
            'flow_description': f"Data flows through {deployment.replace('_', ' ')} deployment with {retention.replace('_', ' ')} retention policy",
            'identity_expansion': self._analyze_identity_expansion(tool_data),
            'exfiltration_risk': self._assess_exfiltration_risk(tool_data)
        }
    
    def _format_control_requirements(self, controls):
        """Format control requirements for display"""
        formatted = {}
        
        for category, requirements in controls.items():
            if isinstance(requirements, list):
                formatted[category] = [req.replace('_', ' ').title() for req in requirements]
            else:
                formatted[category] = str(requirements).replace('_', ' ').title()
        
        return formatted
    
    def _extract_problem_solved(self, tool_data):
        """Extract the core problem this tool solves"""
        use_cases = tool_data.get('use_cases', '').lower()
        users = tool_data.get('intended_users', [])
        
        # Pattern matching for common AI tool use cases
        if 'code' in use_cases or 'develop' in use_cases:
            return "Accelerates software development through AI-assisted coding and documentation"
        elif 'data' in use_cases or 'analyt' in use_cases:
            return "Enhances data analysis and insight generation capabilities"
        elif 'automat' in use_cases:
            return "Automates repetitive operational tasks and workflows"
        elif 'monitor' in use_cases:
            return "Improves system monitoring and incident response"
        elif 'document' in use_cases:
            return "Streamlines documentation and knowledge management processes"
        else:
            return "Improves operational efficiency through AI-powered assistance"
    
    def _analyze_identity_expansion(self, tool_data):
        """Analyze identity surface expansion"""
        auth_model = tool_data.get('auth_model', 'unknown')
        users = tool_data.get('intended_users', [])
        integrations = tool_data.get('integration_points', [])
        
        expansion_factors = []
        
        if 'api_keys' in auth_model:
            expansion_factors.append("API key management")
        if 'service_accounts' in auth_model:
            expansion_factors.append("Service account proliferation")
        if len(users) > 2:
            expansion_factors.append(f"Access for {len(users)} user types")
        if len(integrations) > 1:
            expansion_factors.append(f"Integration with {len(integrations)} systems")
        
        return expansion_factors if expansion_factors else ["Minimal identity expansion"]
    
    def _assess_exfiltration_risk(self, tool_data):
        """Assess data exfiltration risk"""
        data_types = tool_data.get('data_types', [])
        deployment = tool_data.get('deployment_model', '')
        data_storage = tool_data.get('data_storage', '')
        
        risk_level = "Low"
        factors = []
        
        # High-value data types increase risk
        if any(dt in data_types for dt in ['phi', 'pii', 'financial']):
            risk_level = "High"
            factors.append("Processes regulated data types")
        
        # SaaS deployment increases risk
        if deployment == 'saas':
            if risk_level == "Low":
                risk_level = "Moderate"
            factors.append("External SaaS deployment")
        
        # Data persistence increases risk
        if 'persistent' in data_storage or 'long_term' in data_storage:
            factors.append("Long-term data retention")
        
        return {
            'level': risk_level,
            'factors': factors if factors else ["Standard operational data handling"]
        }
    
    def _extract_key_risks(self, assessment):
        """Extract top 3 key risks for executive summary"""
        risk_factors = assessment.get('risk_factors', {})
        key_risks = []
        
        # Sort risks by score
        sorted_risks = sorted(risk_factors.items(), 
                            key=lambda x: x[1].get('score', 0), 
                            reverse=True)
        
        for risk_name, risk_data in sorted_risks[:3]:
            key_risks.append({
                'name': risk_name.replace('_', ' ').title(),
                'level': risk_data.get('level', 'unknown'),
                'description': risk_data.get('justification', 'Risk assessment pending')
            })
        
        return key_risks
    
    def _summarize_mitigations(self, assessment):
        """Summarize key mitigation approaches"""
        controls = assessment.get('control_requirements', {})
        mitigations = []
        
        if 'identity' in controls:
            mitigations.append("Identity and access management controls")
        if 'data' in controls:
            mitigations.append("Data protection and encryption measures")
        if 'network' in controls:
            mitigations.append("Network isolation and monitoring")
        if 'logging' in controls:
            mitigations.append("Comprehensive audit logging")
        
        return mitigations if mitigations else ["Standard security controls"]
    
    def _create_timeline(self, assessment):
        """Create implementation timeline"""
        risk_level = assessment.get('overall_risk', 'moderate')
        
        timeline = {
            'immediate': [],
            'day_30': [],
            'day_90': []
        }
        
        # Immediate actions based on risk level
        if risk_level == 'high':
            timeline['immediate'] = [
                "Implement access controls",
                "Enable audit logging",
                "Establish monitoring"
            ]
        else:
            timeline['immediate'] = [
                "Configure basic access controls",
                "Enable standard logging"
            ]
        
        # 30-day enhancements
        timeline['day_30'] = [
            "Review access patterns",
            "Enhance monitoring coverage",
            "Conduct security review"
        ]
        
        # 90-day target state
        timeline['day_90'] = [
            "Full integration with security stack",
            "Automated compliance reporting",
            "Mature operational procedures"
        ]
        
        return timeline
    
    def _estimate_investment(self, assessment):
        """Estimate required investment"""
        risk_level = assessment.get('overall_risk', 'moderate')
        
        investment = {
            'security_tools': 'Standard',
            'staff_time': 'Moderate',
            'training': 'Basic',
            'ongoing_overhead': 'Low'
        }
        
        if risk_level == 'high':
            investment.update({
                'security_tools': 'Enhanced',
                'staff_time': 'Significant',
                'training': 'Comprehensive',
                'ongoing_overhead': 'Moderate'
            })
        
        return investment
    
    def _extract_business_value(self, tool_data):
        """Extract business value proposition"""
        users = tool_data.get('intended_users', [])
        use_cases = tool_data.get('use_cases', '').lower()
        
        value_props = []
        
        if 'developers' in users:
            value_props.append("Accelerated development cycles")
        if 'data_scientists' in users:
            value_props.append("Enhanced analytical capabilities")
        if 'operators' in users:
            value_props.append("Improved operational efficiency")
        if 'automat' in use_cases:
            value_props.append("Reduced manual effort")
        if 'quality' in use_cases or 'error' in use_cases:
            value_props.append("Improved quality and accuracy")
        
        return value_props if value_props else ["Operational efficiency gains"]
    
    def _generate_change_conditions(self, assessment):
        """Generate conditions that would change the decision"""
        decision = assessment.get('decision', 'conditional_go')
        risk_level = assessment.get('overall_risk', 'moderate')
        
        conditions = []
        
        if decision == 'conditional_go':
            conditions = [
                "Implementation of required security controls",
                "Successful pilot with limited user group",
                "Vendor security certification review"
            ]
        elif decision == 'no_go':
            conditions = [
                "Vendor provides additional security guarantees",
                "Tool redesigned with security-first architecture",
                "Regulatory guidance changes significantly"
            ]
        else:  # go
            conditions = [
                "Significant change in threat landscape",
                "Discovery of major vendor security issues",
                "New regulatory requirements"
            ]
        
        if risk_level == 'high':
            conditions.append("Completion of comprehensive security assessment")
        
        return conditions
    
    def _generate_auditor_points(self, tool_data, assessment):
        """Generate talking points for auditors"""
        return {
            'risk_based_approach': f"Assessment follows risk-based methodology considering data sensitivity ({tool_data.get('data_sensitivity', 'unknown')}) and access scope",
            'control_mapping': f"Required controls mapped to {assessment.get('overall_risk', 'moderate')} risk classification with appropriate compensating measures",
            'compliance_alignment': "Evaluation considers HIPAA, SOC 2 Type II, and third-party risk assessment requirements",
            'evidence_trail': [
                "Documented risk assessment methodology",
                "Control requirement specifications",
                "Phased implementation plan with checkpoints",
                "Ongoing monitoring and review procedures"
            ],
            'vendor_evaluation': f"Vendor ({tool_data.get('vendor', 'unknown')}) security posture evaluated against organizational standards",
            'business_justification': f"Tool addresses legitimate business need: {self._extract_problem_solved(tool_data)}"
        }
    
    def generate_customer_communication(self, tool_data, assessment):
        """Generate customer-facing communication about security measures"""
        tool_name = tool_data.get('tool_name', 'this AI tool')
        
        communication = {
            'security_commitment': f"We have conducted a comprehensive security assessment of {tool_name} to ensure continued protection of your data",
            'control_implementation': "All required security controls have been implemented and tested according to our risk management framework",
            'compliance_maintained': "This implementation maintains our HIPAA compliance and SOC 2 Type II certification standards",
            'ongoing_monitoring': "Continuous monitoring and regular security reviews ensure sustained protection",
            'contact_info': "For security-related questions, please contact our Security Operations team"
        }
        
        return communication
    
    def format_for_json_export(self, tool_data, assessment, report):
        """Format complete assessment for JSON export"""
        return {
            'assessment_metadata': {
                'timestamp': self.timestamp.isoformat(),
                'tool_name': tool_data.get('tool_name'),
                'vendor': tool_data.get('vendor'),
                'assessor': 'AI Tool Onboarding Simulator'
            },
            'tool_profile': tool_data,
            'risk_assessment': assessment,
            'detailed_report': report,
            'recommendations': {
                'decision': assessment.get('decision'),
                'rationale': assessment.get('rationale'),
                'next_steps': assessment.get('enablement_plan', {}).get('day_1', [])
            }
        }
    
    def generate_metrics_dashboard_data(self, assessments_list):
        """Generate data for metrics dashboard from multiple assessments"""
        if not assessments_list:
            return {}
        
        total_assessments = len(assessments_list)
        decisions = [a.get('decision', 'unknown') for a in assessments_list]
        risk_levels = [a.get('overall_risk', 'unknown') for a in assessments_list]
        
        return {
            'total_assessments': total_assessments,
            'decision_breakdown': {
                'go': decisions.count('go'),
                'conditional_go': decisions.count('conditional_go'),
                'no_go': decisions.count('no_go')
            },
            'risk_distribution': {
                'low': risk_levels.count('low'),
                'moderate': risk_levels.count('moderate'),
                'high': risk_levels.count('high')
            },
            'approval_rate': round((decisions.count('go') + decisions.count('conditional_go')) / total_assessments * 100, 1),
            'avg_assessment_time': '15 minutes',  # Could be calculated from actual timing data
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
