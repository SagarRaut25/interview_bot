$(document).ready(function() {
    // Update question count display
    $('#numQuestions').on('input', function() {
        $('#questionCount').text($(this).val());
    });

    // Start interview
    $('#startInterviewBtn').click(function() {
        const role = $('#role').val();
        const numQuestions = $('#numQuestions').val();
        
        $(this).prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Starting...');
        
        $.ajax({
            url: '/interview/start_interview',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                role: role,
                num_questions: numQuestions
            }),
            success: function(response) {
                if (response.status === 'started') {
                    $('.setup-section').hide();
                    $('.interview-section').show();
                    addMessage('bot', response.greeting);
                    updateProgress(1, response.total_questions);
                    getNextQuestion();
                }
            },
            error: function(xhr) {
                alert('Error starting interview: ' + xhr.responseJSON?.message || 'Unknown error');
            },
            complete: function() {
                $('#startInterviewBtn').prop('disabled', false).html('<i class="fas fa-play"></i> Start Interview');
            }
        });
    });

    // Submit answer
    $('#answerForm').submit(function(e) {
        e.preventDefault();
        const answer = $('#answerText').val().trim();
        
        if (answer === '') {
            alert('Please enter your answer');
            return;
        }
        
        $('#submitAnswerBtn').prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Submitting...');
        
        $.ajax({
            url: '/interview/submit_answer',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                answer: answer
            }),
            success: function(response) {
                if (response.status === 'answer_submitted') {
                    addMessage('user', answer);
                    updateProgress(response.current_question, response.total_questions);
                    
                    if (response.current_question < response.total_questions) {
                        getNextQuestion();
                    } else {
                        generateReport();
                    }
                }
            },
            error: function(xhr) {
                alert('Error submitting answer: ' + xhr.responseJSON?.message || 'Unknown error');
            },
            complete: function() {
                $('#submitAnswerBtn').prop('disabled', false).html('Submit Answer <i class="fas fa-paper-plane"></i>');
                $('#answerText').val('');
            }
        });
    });

    // Record audio button
    $('#recordBtn').click(function() {
        $(this).prop('disabled', true).html('<i class="fas fa-microphone-alt-slash"></i> Recording...');
        
        $.ajax({
            url: '/record_audio',
            type: 'POST',
            success: function(response) {
                if (response.status === 'success') {
                    alert('Audio recorded successfully!');
                } else {
                    alert('Recording failed: ' + response.message);
                }
            },
            error: function(xhr) {
                alert('Error recording audio: ' + xhr.responseJSON?.message || 'Unknown error');
            },
            complete: function() {
                $('#recordBtn').prop('disabled', false).html('<i class="fas fa-microphone"></i> Record Answer');
            }
        });
    });

    // Generate report
    function generateReport() {
        $.ajax({
            url: '/report/generate_report',
            type: 'POST',
            success: function(response) {
                if (response.status === 'success') {
                    $('.interview-section').hide();
                    $('.report-section').show();
                    
                    // Display summary
                    let summaryHtml = `
                        <h4>Interview Results</h4>
                        <div class="result-card mb-3 p-3 bg-light rounded">
                            <div class="d-flex justify-content-between">
                                <span><strong>Overall Rating:</strong></span>
                                <span class="badge bg-primary">${response.avg_rating.toFixed(1)}/10</span>
                            </div>
                            <div class="d-flex justify-content-between mt-2">
                                <span><strong>Decision:</strong></span>
                                <span class="badge ${response.decision === 'SELECTED' ? 'bg-success' : 
                                    response.decision === 'UNDER CONSIDERATION' ? 'bg-warning' : 'bg-danger'}">
                                    ${response.decision}
                                </span>
                            </div>
                        </div>
                        <h5 class="mt-4">Detailed Feedback</h5>
                        <div class="feedback-text">${formatReportText(response.report)}</div>
                    `;
                    
                    $('#reportSummary').html(summaryHtml);
                    
                    // Set up download button
                    $('#downloadReportBtn').off('click').click(function() {
                        window.location.href = `/download_report/${response.report_filename}`;
                    });
                }
            },
            error: function(xhr) {
                alert('Error generating report: ' + xhr.responseJSON?.message || 'Unknown error');
            }
        });
    }

    // Restart interview
    $('#restartInterviewBtn').click(function() {
        $('.report-section').hide();
        $('.setup-section').show();
        $('#conversationContainer').empty();
        $.get('/', function() {
            // Reload the page to reset everything
            location.reload();
        });
    });

    // Helper functions
    function getNextQuestion() {
        $.ajax({
            url: '/interview/get_question',
            type: 'GET',
            success: function(response) {
                if (response.status === 'completed') {
                    generateReport();
                } else if (response.text) {
                    addMessage('bot', response.text);
                } else if (response.status === 'not_started') {
                    alert('Interview not started. Please start the interview first.');
                }
            },
            error: function(xhr) {
                alert('Error getting question: ' + xhr.responseJSON?.message || 'Unknown error');
            }
        });
    }

    function addMessage(speaker, text) {
        const messageClass = speaker === 'bot' ? 'bot-message' : 'user-message';
        const icon = speaker === 'bot' ? '<i class="fas fa-robot me-2"></i>' : '<i class="fas fa-user me-2"></i>';
        
        const messageHtml = `
            <div class="message ${messageClass} d-flex">
                ${icon}
                <div>${text.replace(/\n/g, '<br>')}</div>
            </div>
        `;
        
        $('#conversationContainer').append(messageHtml);
        $('#conversationContainer').scrollTop($('#conversationContainer')[0].scrollHeight);
    }

    function formatReportText(text) {
        return text.replace(/\n/g, '<br>')
                   .replace(/=== (.*?) ===/g, '<h5>$1</h5>')
                   .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    }
});