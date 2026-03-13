import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path
from analyzer import Conversation
import plotme
from typing import List, Optional

app = typer.Typer(help="Modern Messenger Analyzer CLI")
console = Console()

@app.command()
def stats(
    folder: str = typer.Argument(..., help="Folder name in MessagesSources"),
    save: bool = typer.Option(False, "--save", "-s", help="Save stats to a text file")
):
    """Display comprehensive statistics for a conversation."""
    path = Path("MessagesSources") / folder
    if not path.exists():
        console.print(f"[red]Error: Folder {path} not found![/red]")
        raise typer.Exit(code=1)

    console.print(f"[green]Loading conversation from {path}...[/green]")
    try:
        conv = Conversation(str(path))
    except Exception as e:
        console.print(f"[red]Error loading data: {e}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"\n[bold underline]Conversation Stats: {folder}[/bold underline]")
    console.print(f"Total Messages: [bold]{conv.get_total_messages()}[/bold]")
    console.print(f"Span: {conv.span.days} days ({conv.span.days/365:.2f} years)")
    console.print(f"Participants: {', '.join(conv.participants)}")

    # Messages Per Participant Table
    table = Table(title="Messages Per Participant")
    table.add_column("Participant", style="cyan")
    table.add_column("Messages", style="magenta")
    per_p = conv.get_messages_per_participant()
    for p, count in per_p.items():
        table.add_row(p, f"{count:,}")
    console.print(table)

    # Top Days
    console.print("\n[bold]Top 5 Messaging Days:[/bold]")
    for day, count in conv.get_top_days().items():
        console.print(f"  {day}: {count} messages")

    # Word Stats
    console.print(f"\n[bold]Unique Words:[/bold] {conv.get_unique_word_count()}")
    console.print("[bold]Most Common Words:[/bold]")
    for word, count in conv.get_most_common_words(5).items():
        console.print(f"  {word}: {count}")

    # Message Types
    table_types = Table(title="Message Types")
    table_types.add_column("Type", style="cyan")
    table_types.add_column("Count", style="magenta")
    for mtype, count in conv.get_message_types().items():
        table_types.add_row(mtype, str(count))
    console.print(table_types)

    if save:
        save_stats(conv, folder)

def save_stats(conv: Conversation, filename: str):
    """Saves the stats to a text file."""
    output_path = Path(f"{filename}-stats.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Welcome to your stats for your conversation with {filename}\n\n")
        f.write(f"The conversation spans {conv.span.days} days or {conv.span.days/365:.2f} years\n\n")
        f.write(f"You have exchanged {conv.get_total_messages()} messages in total!\n\n")
        
        f.write("Messages breakdown:\n")
        for k, v in conv.get_messages_per_participant().items():
            f.write(f"\t{k} : {v}\n")
        
        f.write("\nYour top 5 messaging days were:\n")
        for k, v in conv.get_top_days().items():
            f.write(f"\t{k} : {v}\n")
            
        month, count = conv.get_month_with_most_messages()
        f.write(f"\nThe month with the most messages was:\n\t{month} with {count} messages\n\n")
        
        avg_resp = conv.get_response_times().mean()
        f.write(f"Global average response time in conversation: {avg_resp:.1f} seconds or {avg_resp/60:.2f} minutes\n\n")

        f.write("Average response time of each participant:\n")
        for k, v in conv.get_average_response_time_per_participant().items():
            f.write(f"\t{k} : {v:.2f}s | {v/60:.2f}m\n")

        f.write(f"\nAverage words per message: {conv.get_average_words_per_message():.2f}\n")
        
        f.write("\nPer participant breakdown (Message Types):\n")
        type_df = conv.get_messages_per_type_per_participant()
        for p, row in type_df.iterrows():
            f.write(f"\t{p}:\n\t\t")
            types_str = ", ".join([f"{k} : {v}" for k, v in row.to_dict().items()])
            f.write(f"{types_str}\n")

        f.write("\nYour 5 most common words were:\n")
        for k, v in conv.get_most_common_words(5).items():
            f.write(f"\t{k} : {v} times\n")
        
        f.write(f"\nWow you used {conv.get_unique_word_count()} unique words!\n")
        f.write("\n ----- END OF STATS -----\n")
    console.print(f"[green]Stats saved to {output_path}[/green]")

@app.command()
def plot(
    folder: str = typer.Argument(..., help="Folder name in MessagesSources"),
    type: str = typer.Option("daily", "--type", "-t", help="daily, monthly, hourly, weekday, participant, words, response"),
    participant: bool = typer.Option(False, "--participant", "-p", help="Break down by participant where applicable"),
    keywords: Optional[str] = typer.Option(None, "--keywords", "-k", help="Comma-separated keywords for daily plot"),
    unit: str = typer.Option("Seconds", "--unit", "-u", help="Time unit for response plots (Seconds, Minutes, Hours)")
):
    """Generate various plots for the conversation."""
    path = Path("MessagesSources") / folder
    conv = Conversation(str(path))

    if type == "daily":
        if keywords:
            kw_list = [k.strip() for k in keywords.split(",")]
            data = conv.get_messages_per_day(words=kw_list).to_dict()
            data = {k.strftime('%Y %m %d'): v for k, v in data.items()}
            plotme.plotLineGraph_MessagesPerDay(data, kw_list)
        elif participant:
            data = conv.get_messages_per_day_per_participant()
            plot_data = {str(k): v.to_dict() for k, v in data.iterrows()}
            plotme.plotLineGraph_MessagesPerDayPerParticipant(plot_data, conv.participants, False)
        else:
            data = conv.get_messages_per_day().to_dict()
            data = {k.strftime('%Y %m %d'): v for k, v in data.items()}
            plotme.plotLineGraph_MessagesPerDay(data)
    
    elif type == "monthly":
        if participant:
            data = conv.get_messages_per_month_per_participant()
            plot_data = data.to_dict(orient='index')
            plotme.plotBarGraph_MessagesPerMonthPerParticipant(plot_data, conv.participants)
        else:
            data = conv.get_messages_per_month().to_dict()
            data = {f"{k.year} {k.strftime('%B')}": v for k, v in data.items()}
            plotme.plotBarGraph_MessagesPerMonth(data)
    
    elif type == "weekday":
        data = conv.get_messages_per_weekday().to_dict()
        plotme.plotSpiderGraph(data)
        
    elif type == "hourly":
        data = conv.get_messages_per_hour().to_dict()
        plotme.plotSpiderGraph(data)

    elif type == "participant":
        data = conv.get_messages_per_participant(include_total=True)
        plotme.plotBarGraph_TotalMessages_PerParticipant(data)

    elif type == "words":
        data = conv.get_average_words_per_message_per_month().to_dict()
        plotme.plotBarGraph_AveragePerMonth_General(data, title='Words Per Message')

    elif type == "response":
        data_s = conv.get_average_response_time_per_month()
        divisor = 1
        if unit == "Minutes": divisor = 60
        elif unit == "Hours": divisor = 3600
        data = (data_s / divisor).to_dict()
        plotme.plotBarGraph_MessagesPerMonth(data, title='Average Response Time', time=unit)

@app.command()
def search(
    folder: str = typer.Argument(..., help="Folder name in MessagesSources"),
    word: str = typer.Argument(..., help="Word to search for")
):
    """Count appearances of a specific word."""
    path = Path("MessagesSources") / folder
    conv = Conversation(str(path))
    count = conv.get_word_appearances(word)
    console.print(f"The word '[bold]{word}[/bold]' appears [bold]{count}[/bold] times.")

if __name__ == "__main__":
    app()
