import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

class Conversation:
    def __init__(self, folder_path: str):
        self.folder_path = Path(folder_path)
        self.df: pd.DataFrame = self._load_data()
        self.participants: List[str] = self.df['sender_name'].unique().tolist()
        self._calculate_span()

    def _load_data(self) -> pd.DataFrame:
        messages = []
        json_files = sorted(self.folder_path.glob("message_*.json"))
        
        if not json_files:
            raise FileNotFoundError(f"No message_*.json files found in {self.folder_path}")

        for file_path in json_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for message in data['messages']:
                    # Handle Messenger's encoding quirk
                    if 'sender_name' in message:
                        message['sender_name'] = message['sender_name'].encode('latin1').decode('utf-8')
                    if 'content' in message:
                        message['content'] = message['content'].encode('latin1').decode('utf-8')
                    messages.append(message)
        
        df = pd.DataFrame(messages)
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp_ms'], unit='ms')
        # Sort by timestamp (Messenger data is usually newest first)
        df = df.sort_values('timestamp').reset_index(drop=True)
        return df

    def _calculate_span(self):
        self.start_date = self.df['timestamp'].min()
        self.end_date = self.df['timestamp'].max()
        self.span = self.end_date - self.start_date

    def get_total_messages(self) -> int:
        return len(self.df)

    def get_messages_per_participant(self, include_total: bool = False) -> Dict[str, int]:
        counts = self.df['sender_name'].value_counts().to_dict()
        if include_total:
            counts['Total'] = len(self.df)
        return counts

    def get_messages_per_day(self, words: Optional[List[str]] = None) -> pd.Series:
        df = self.df
        if words:
            # pattern = '|'.join(words)
            # Use a more robust word matching to match original behavior
            mask = df['content'].fillna('').apply(lambda x: any(w in x.split() for w in words))
            df = df[mask]
        
        return df.groupby(df['timestamp'].dt.date).size()

    def get_messages_per_month(self) -> pd.Series:
        return self.df.groupby(self.df['timestamp'].dt.to_period('M')).size()

    def get_messages_per_day_per_participant(self) -> pd.DataFrame:
        return self.df.groupby([self.df['timestamp'].dt.date, 'sender_name']).size().unstack(fill_value=0)

    def get_messages_per_month_per_participant(self) -> pd.DataFrame:
        # Reformat index for plotme compatibility: '2020 February'
        data = self.df.groupby([self.df['timestamp'].dt.to_period('M'), 'sender_name']).size().unstack(fill_value=0)
        data.index = data.index.map(lambda x: f"{x.year} {x.strftime('%B')}")
        return data

    def get_messages_per_weekday(self) -> pd.Series:
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        counts = self.df['timestamp'].dt.day_name().value_counts()
        return counts.reindex(weekdays, fill_value=0)

    def get_messages_per_hour(self) -> pd.Series:
        return self.df['timestamp'].dt.hour.value_counts().sort_index()

    def get_average_words_per_message(self) -> float:
        text_messages = self.df[self.df['content'].notna()]
        if text_messages.empty:
            return 0.0
        word_counts = text_messages['content'].str.split().str.len()
        return word_counts.mean()

    def get_average_words_per_message_per_participant(self) -> Dict[str, float]:
        text_messages = self.df[self.df['content'].notna()].copy()
        if text_messages.empty:
            return {p: 0.0 for p in self.participants}
        text_messages['word_count'] = text_messages['content'].str.split().str.len()
        return text_messages.groupby('sender_name')['word_count'].mean().to_dict()

    def get_average_words_per_message_per_month(self) -> pd.Series:
        text_messages = self.df[self.df['content'].notna()].copy()
        if text_messages.empty:
            return pd.Series()
        text_messages['word_count'] = text_messages['content'].str.split().str.len()
        res = text_messages.groupby(text_messages['timestamp'].dt.to_period('M'))['word_count'].mean()
        res.index = res.index.map(lambda x: f"{x.year} {x.strftime('%B')}")
        return res

    def get_most_common_words(self, limit: int = 10) -> Dict[str, int]:
        text_messages = self.df[self.df['content'].notna()]
        if text_messages.empty:
            return {}
        words = text_messages['content'].str.split(expand=True).stack()
        return words.value_counts().head(limit).to_dict()

    def get_unique_word_count(self) -> int:
        text_messages = self.df[self.df['content'].notna()]
        if text_messages.empty:
            return 0
        words = text_messages['content'].str.split(expand=True).stack()
        return words.nunique()

    def get_word_appearances(self, word: str) -> int:
        text_messages = self.df[self.df['content'].notna()]
        return text_messages['content'].apply(lambda x: x.split().count(word)).sum()

    def get_message_types(self) -> Dict[str, int]:
        cols = self.df.columns
        types = {
            'Text messages': self.df['content'].notna().sum(),
            'Photos': self.df['photos'].notna().sum() if 'photos' in cols else 0,
            'Videos': self.df['videos'].notna().sum() if 'videos' in cols else 0,
            'Voice recordings': self.df['audio_files'].notna().sum() if 'audio_files' in cols else 0,
            'gifs': self.df['gifs'].notna().sum() if 'gifs' in cols else 0,
            'Shares': self.df['share'].notna().sum() if 'share' in cols else 0,
            'Voice calls': self.df['call_duration'].notna().sum() if 'call_duration' in cols else 0,
        }
        return types

    def get_messages_per_type_per_participant(self) -> pd.DataFrame:
        cols = self.df.columns
        data = {}
        data['Text messages'] = self.df[self.df['content'].notna()].groupby('sender_name').size()
        
        type_mapping = {
            'photos': 'Photos',
            'videos': 'Videos',
            'audio_files': 'Voice recordings',
            'gifs': 'gifs',
            'share': 'Shares',
            'call_duration': 'Voice calls'
        }
        
        for col, label in type_mapping.items():
            if col in cols:
                data[label] = self.df[self.df[col].notna()].groupby('sender_name').size()
            else:
                data[label] = pd.Series(0, index=self.participants)
                
        return pd.DataFrame(data).fillna(0).astype(int)

    def get_response_times(self) -> pd.Series:
        df = self.df.copy()
        df['prev_sender'] = df['sender_name'].shift(1)
        df['prev_timestamp'] = df['timestamp'].shift(1)
        
        responses = df[df['sender_name'] != df['prev_sender']].copy()
        responses['response_time'] = (responses['timestamp'] - responses['prev_timestamp']).dt.total_seconds()
        
        return responses['response_time'].dropna()

    def get_average_response_time_per_participant(self) -> Dict[str, float]:
        df = self.df.copy()
        df['prev_sender'] = df['sender_name'].shift(1)
        df['prev_timestamp'] = df['timestamp'].shift(1)
        
        responses = df[df['sender_name'] != df['prev_sender']].copy()
        responses['response_time'] = (responses['timestamp'] - responses['prev_timestamp']).dt.total_seconds()
        
        return responses.groupby('sender_name')['response_time'].mean().to_dict()

    def get_average_response_time_per_month(self) -> pd.Series:
        df = self.df.copy()
        df['prev_sender'] = df['sender_name'].shift(1)
        df['prev_timestamp'] = df['timestamp'].shift(1)
        
        responses = df[df['sender_name'] != df['prev_sender']].copy()
        responses['response_time'] = (responses['timestamp'] - responses['prev_timestamp']).dt.total_seconds()
        
        res = responses.groupby(responses['timestamp'].dt.to_period('M'))['response_time'].mean()
        res.index = res.index.map(lambda x: f"{x.year} {x.strftime('%B')}")
        return res

    def get_top_days(self, limit: int = 5) -> Dict[str, int]:
        return self.get_messages_per_day().sort_values(ascending=False).head(limit).to_dict()

    def get_month_with_most_messages(self) -> Tuple[str, int]:
        per_month = self.get_messages_per_month()
        if per_month.empty:
            return ("None", 0)
        max_month = per_month.idxmax()
        return (f"{max_month.year} {max_month.strftime('%B')}", per_month[max_month])
