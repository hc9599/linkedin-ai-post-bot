"""
Is this article actually about C# / .NET?

Hacker News search is sloppy. "csharp" can match "South Korea youth employment
falls sharply". We only keep posts that mention a real .NET word.
"""
DOTNET_RELEVANCE_KEYWORDS = [
    "dotnet", ".net", "csharp", "c#", "asp.net", "blazor",
    "entity framework", "nuget", "roslyn", "maui", "xamarin",
    "azure functions", "visual studio", "rider", "minimal api",
    "orleans", "signalr", "ef core", "wpf", "winforms",
]


def is_dotnet_relevant(title: str, summary: str) -> bool:
    """True if the headline or blurb mentions C# / .NET stuff."""
    text = (title + " " + summary).lower()
    return any(kw in text for kw in DOTNET_RELEVANCE_KEYWORDS)
