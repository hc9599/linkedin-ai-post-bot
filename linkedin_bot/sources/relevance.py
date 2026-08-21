DOTNET_RELEVANCE_KEYWORDS = [
    "dotnet", ".net", "csharp", "c#", "asp.net", "blazor",
    "entity framework", "nuget", "roslyn", "maui", "xamarin",
    "azure functions", "visual studio", "rider", "minimal api",
    "orleans", "signalr", "ef core", "wpf", "winforms",
]


def is_dotnet_relevant(title: str, summary: str) -> bool:
    """Returns True if the title or summary contains at least one .NET/C# keyword."""
    text = (title + " " + summary).lower()
    return any(kw in text for kw in DOTNET_RELEVANCE_KEYWORDS)
