from core.providers.base import PRProvider, PR, DeployStatus
from core.notifiers.base import Notifier


def get_provider(config) -> PRProvider:
    if config.provider.type == "azure_devops":
        from core.providers.azure_devops import AzureDevOpsProvider
        return AzureDevOpsProvider(config.provider)
    if config.provider.type == "github":
        from core.providers.github import GitHubProvider
        return GitHubProvider(config.provider)
    if config.provider.type == "bitbucket":
        from core.providers.bitbucket import BitbucketProvider
        return BitbucketProvider(config.provider)
    raise ValueError(f"Provider no soportado: {config.provider.type}")


def get_notifier(config) -> Notifier:
    if config.notifier.type == "slack":
        from core.notifiers.slack import SlackNotifier
        return SlackNotifier(config.notifier)
    if config.notifier.type == "teams":
        from core.notifiers.teams import TeamsNotifier
        return TeamsNotifier(config.notifier)
    raise ValueError(f"Notifier no soportado: {config.notifier.type}")
