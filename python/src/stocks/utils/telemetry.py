from loguru import logger


class AgentTelemetry:
    """Quantitative observability module monitoring agent latency, SQL executions, and token metrics."""

    @staticmethod
    def log_agent_execution(agent_name: str, duration_seconds: float, token_count: int = 0) -> None:
        """Logs structured diagnostic metrics for individual agent LLM invocations."""
        logger.info(
            f"[Telemetry] Agent: {agent_name} | "
            f"Latency: {duration_seconds:.3f}s | "
            f"Tokens: {token_count if token_count > 0 else 'N/A'} | "
            f"Status: SUCCESS"
        )

    @staticmethod
    def log_sql_execution(query: str, duration_seconds: float, row_count: int) -> None:
        """Logs structured performance metrics for agent-generated SQL queries."""
        # Sanitize query preview
        query_preview = " ".join(query.strip().split())[:60]
        logger.info(
            f"[Telemetry] SQL Execution | "
            f'Query: "{query_preview}..." | '
            f"Latency: {duration_seconds:.3f}s | "
            f"Rows Fetched: {row_count}"
        )

    @staticmethod
    def log_workflow_completion(workflow_name: str, duration_seconds: float, status: str = "SUCCESS") -> None:
        """Logs aggregate operational performance for a full multi-agent pipeline."""
        logger.info(
            f"[Telemetry] Workflow: {workflow_name} | "
            f"Total Duration: {duration_seconds:.3f}s | "
            f"Status: {status.upper()}"
        )
