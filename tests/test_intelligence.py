import unittest

from cleepwheel.intelligence import classify_text


class IntelligenceTest(unittest.TestCase):
    def test_classifies_song_lyrics(self):
        text = """Verso 1
Camino solo por la ciudad
Buscando el brillo de tu voz
Coro
Otra vez vuelvo a cantar
Otra vez vuelvo a cantar"""

        classification = classify_text(text)

        self.assertEqual(classification.category, "song")
        self.assertIn("lyrics", classification.tags)
        self.assertIn("music", classification.tags)

    def test_classifies_audio_files_as_songs(self):
        classification = classify_text("Black Mamba - Demo Mix.wav")

        self.assertEqual(classification.category, "song")
        self.assertIn("audio-file", classification.tags)

    def test_classifies_credentials_as_sensitive(self):
        classification = classify_text("api_key=1234567890abcdef")

        self.assertEqual(classification.category, "credential")
        self.assertEqual(classification.sensitivity, "sensitive")

    def test_classifies_metacommands(self):
        classification = classify_text("Clasifica esta letra de cancion por energia y mood")

        self.assertEqual(classification.category, "metacommand")
        self.assertIn("instruction", classification.tags)
