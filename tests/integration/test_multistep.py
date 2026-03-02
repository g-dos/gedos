"""
Integration tests for multi-step task execution.
"""
import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

# Import Gedos modules
from interfaces.telegram_bot import _run_task_with_progress_updates, _task_status, _task_cancelled
from core.task_planner import plan_task, TaskStep, TaskPlan
from agents.terminal_agent import execute_step as terminal_execute_step


class TestMultiStepExecution:
    """Test multi-step task execution functionality."""
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update."""
        user = User(id=12345, first_name="Test", is_bot=False)
        chat = Chat(id=12345, type="private")
        message = Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=user,
            text="/task test command"
        )
        update = Update(update_id=1, message=message)
        return update
    
    @pytest.fixture
    def mock_progress_msg(self):
        """Create a mock progress message."""
        msg = AsyncMock()
        msg.edit_text = AsyncMock()
        return msg
    
    @pytest.mark.asyncio
    async def test_three_step_terminal_task_sequence(self, mock_update, mock_progress_msg):
        """Test that a 3-step terminal task executes in sequence."""
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the task planner to return a 3-step plan
            steps = [
                TaskStep(agent="terminal", action=f"cd {temp_dir}"),
                TaskStep(agent="terminal", action="echo 'hello world' > test.txt"),
                TaskStep(agent="terminal", action="cat test.txt")
            ]
            plan = TaskPlan(original_task="create and read test file", steps=steps)
            
            with patch('core.task_planner.plan_task', return_value=plan):
                with patch('core.task_planner._is_multi_step_task', return_value=True):
                    # Execute the multi-step task
                    result = await _run_task_with_progress_updates(
                        "create and read test file",
                        mock_progress_msg,
                        12345,
                        mock_update
                    )
            
            # Verify task completed successfully
            assert result["success"] is True
            assert "multi-step" in result["agent_used"]
            
            # Verify progress messages were sent
            assert mock_progress_msg.edit_text.call_count >= 3  # At least one per step
            
            # Verify the file was actually created and contains expected content
            test_file = os.path.join(temp_dir, "test.txt")
            assert os.path.exists(test_file)
            with open(test_file, 'r') as f:
                content = f.read().strip()
                assert content == "hello world"
    
    @pytest.mark.asyncio
    async def test_failed_step_triggers_retry(self, mock_update, mock_progress_msg):
        """Test that a failed step triggers retry logic."""
        # Create a step that will fail
        steps = [
            TaskStep(agent="terminal", action="nonexistent_command_that_will_fail"),
        ]
        plan = TaskPlan(original_task="test failure", steps=steps)
        
        with patch('core.task_planner.plan_task', return_value=plan):
            with patch('core.task_planner._is_multi_step_task', return_value=True):
                # Mock user decision to continue (simulate /yes)
                with patch('interfaces.telegram_bot._pending_step_decision', {}):
                    # Execute the task - it should fail but handle gracefully
                    result = await _run_task_with_progress_updates(
                        "test failure",
                        mock_progress_msg,
                        12345,
                        mock_update
                    )
        
        # Task should complete but with failure
        assert result["success"] is False
        
        # Should have attempted progress updates (including retry messages)
        call_args = [call[0][0] for call in mock_progress_msg.edit_text.call_args_list]
        retry_messages = [msg for msg in call_args if "Retrying" in msg or "failed" in msg]
        assert len(retry_messages) > 0
    
    @pytest.mark.asyncio
    async def test_stop_cancels_mid_execution(self, mock_update, mock_progress_msg):
        """Test that /stop command cancels multi-step execution."""
        global _task_cancelled
        
        # Create a multi-step task
        steps = [
            TaskStep(agent="terminal", action="echo 'step 1'"),
            TaskStep(agent="terminal", action="echo 'step 2'"),
            TaskStep(agent="terminal", action="echo 'step 3'")
        ]
        plan = TaskPlan(original_task="test cancellation", steps=steps)
        
        # Mock cancellation after first step
        original_execute = terminal_execute_step
        call_count = 0
        
        def mock_execute_with_cancel(step):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First step succeeds
                return original_execute(step)
            else:
                # Simulate cancellation before subsequent steps
                global _task_cancelled
                _task_cancelled = True
                return original_execute(step)
        
        with patch('core.task_planner.plan_task', return_value=plan):
            with patch('core.task_planner._is_multi_step_task', return_value=True):
                with patch('agents.terminal_agent.execute_step', side_effect=mock_execute_with_cancel):
                    # Reset cancellation state
                    _task_cancelled = False
                    
                    # Execute the task
                    result = await _run_task_with_progress_updates(
                        "test cancellation",
                        mock_progress_msg,
                        12345,
                        mock_update
                    )
        
        # Task should be cancelled
        assert result.get("success") is False
        
        # Should have progress messages indicating cancellation
        call_args = [call[0][0] for call in mock_progress_msg.edit_text.call_args_list]
        cancel_messages = [msg for msg in call_args if "cancel" in msg.lower() or "stop" in msg.lower()]
        
        # Reset global state
        _task_cancelled = False


class TestTerminalSelfCorrection:
    """Test terminal agent self-correction functionality."""
    
    def test_successful_command_no_correction(self):
        """Test that successful commands don't trigger correction."""
        step = TaskStep(agent="terminal", action="echo 'success'")
        result = terminal_execute_step(step)
        
        assert result["success"] is True
        assert "success" in result["result"]
        assert "Self-corrected" not in result["result"]
    
    def test_failed_command_attempts_correction(self):
        """Test that failed commands attempt LLM correction."""
        with patch('agents.terminal_agent._correct_command_with_llm') as mock_correct:
            # Mock LLM to suggest a corrected command
            mock_correct.return_value = "echo 'corrected'"
            
            # Mock successful retry
            with patch('agents.terminal_agent.run_shell') as mock_shell:
                # First call fails, second call succeeds
                failed_result = Mock()
                failed_result.success = False
                failed_result.stderr = "command not found"
                failed_result.stdout = ""
                
                success_result = Mock()
                success_result.success = True
                success_result.stdout = "corrected"
                success_result.stderr = ""
                
                mock_shell.side_effect = [failed_result, success_result]
                
                step = TaskStep(agent="terminal", action="nonexistent_command")
                result = terminal_execute_step(step)
        
        # Should have attempted correction and succeeded
        mock_correct.assert_called_once()
        assert result["success"] is True
        assert "Self-corrected" in result["result"]
    
    def test_correction_fails_returns_original_error(self):
        """Test that if correction also fails, original error is returned."""
        with patch('agents.terminal_agent._correct_command_with_llm') as mock_correct:
            # Mock LLM to suggest same command (no correction)
            mock_correct.return_value = "nonexistent_command"
            
            step = TaskStep(agent="terminal", action="nonexistent_command")
            result = terminal_execute_step(step)
        
        # Should have failed without correction
        assert result["success"] is False
        assert "Self-corrected" not in result["result"]


if __name__ == "__main__":
    pytest.main([__file__])