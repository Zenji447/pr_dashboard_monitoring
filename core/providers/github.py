from core.providers.base import PRProvider, PR, DeployStatus


class GitHubProvider(PRProvider):
    def __init__(self, config):
        self.config = config

    def get_active_prs(self) -> list[PR]: raise NotImplementedError
    def get_completed_prs(self, date_from, date_to) -> list[PR]: raise NotImplementedError
    def approve(self, pr_id): raise NotImplementedError
    def reject(self, pr_id, comment): raise NotImplementedError
    def complete(self, pr_id): raise NotImplementedError
    def get_deploy_status(self, pr) -> DeployStatus: raise NotImplementedError
