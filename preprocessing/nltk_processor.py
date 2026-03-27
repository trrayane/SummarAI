import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.probability import FreqDist
import string

nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('stopwords', quiet=True)

class NLTKProcessor:
    def __init__(self, language='english'):
        self.stop_words = set(stopwords.words(language))

    def preprocess(self, text: str) -> dict:
        sentences = sent_tokenize(text)
        words = word_tokenize(text.lower())

        # Suppression stop-words et ponctuation
        filtered_words = [
            w for w in words
            if w not in self.stop_words and w not in string.punctuation
        ]

        # Fréquence des mots
        freq_dist = FreqDist(filtered_words)

        # Score de chaque phrase
        sentence_scores = {}
        for sent in sentences:
            for word in word_tokenize(sent.lower()):
                if word in freq_dist:
                    sentence_scores[sent] = sentence_scores.get(sent, 0) + freq_dist[word]

        # Top phrases clés (30% du texte)
        n = max(1, len(sentences) // 3)
        top_sentences = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:n]
        key_content = " ".join(top_sentences)

        return {
            "original_text": text,
            "key_sentences": top_sentences,
            "key_content": key_content,
            "word_count": len(words),
            "sentence_count": len(sentences)
        }