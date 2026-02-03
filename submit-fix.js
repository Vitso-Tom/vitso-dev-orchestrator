    async submitAssessment(e) {
        e.preventDefault();

        if (!this.validateCurrentStep()) {
            return;
        }

        const submitBtn = document.getElementById('submit-btn');
        const originalText = submitBtn.textContent;

        try {
            // Show loading state
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing Assessment...';

            // Collect form data
            const form = document.getElementById('assessment-form');
            const formData = new FormData(form);

            // Convert FormData to JSON
            const jsonData = {};
            formData.forEach((value, key) => {
                if (jsonData[key]) {
                    if (!Array.isArray(jsonData[key])) {
                        jsonData[key] = [jsonData[key]];
                    }
                    jsonData[key].push(value);
                } else {
                    jsonData[key] = value;
                }
            });

            // Submit assessment as JSON
            const response = await fetch('/assess', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(jsonData)
            });

            const result = await response.json();

            if (result.success) {
                // Redirect to results
                window.location.href = `/results/${result.data.assessment_id}`;
            } else {
                this.showError('Assessment failed: ' + (result.error || 'Unknown error'));
            }

        } catch (error) {
            console.error('Submission error:', error);
            this.showError('Failed to submit assessment. Please try again.');
        } finally {
            // Restore button state
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    }