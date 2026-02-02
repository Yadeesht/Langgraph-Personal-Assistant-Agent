from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


# This class does the short-term memory thing by adding ad summerizing the context in real-time
class AsyncSqliteSaver(AsyncSqliteSaver):
    async def aput(self, config, checkpoint, metadata, new_versions):
        """Save checkpoint with cleaned messages"""

        return await super().aput(config, checkpoint, metadata, new_versions)
