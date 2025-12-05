from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import os, re, time, pickle

TFIDF_MODEL_PATH = "tfidf_model.pkl"
_tfidf_vectorizer = None
_files_changed_since_rebuild = 0
_rebuild_threshold = 5  # Rebuild after N file changes
_reindex_callback = None  # Callback for re-indexing files

def _get_git_files():
    """Get all files tracked by git."""
    import subprocess
    try:
        result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, check=True)
        return [f for f in result.stdout.strip().split('\n') if f.endswith(('.py', '.js', '.ts', '.java', '.go'))]
    except:
        return []

def _load_tfidf_model():
    """Load the TF-IDF model from disk if it exists."""
    global _tfidf_vectorizer
    start_time = time.time()
    if _tfidf_vectorizer is None and os.path.exists(TFIDF_MODEL_PATH):
        with open(TFIDF_MODEL_PATH, 'rb') as f:
            _tfidf_vectorizer = pickle.load(f)
        end_time = time.time()
        print(f"Model load time: {(end_time - start_time)*1000:.2f} ms")
    return _tfidf_vectorizer

def _save_tfidf_model(vectorizer):
    """Save the TF-IDF model to disk."""
    global _tfidf_vectorizer
    start_time = time.time()
    _tfidf_vectorizer = vectorizer
    with open(TFIDF_MODEL_PATH, 'wb') as f:
        pickle.dump(vectorizer, f)
    end_time = time.time()
    print(f"Model save time: {(end_time - start_time)*1000:.2f} ms")

def rebuild_tfidf_model(force=False, reindex_callback=None):
    """
    Rebuild the TF-IDF model from all git-tracked code files.

    Args:
        force: Force rebuild even if model is recent
        reindex_callback: Optional function to call for re-indexing files (signature: callable(filepath))
    """
    global _files_changed_since_rebuild, _reindex_callback
    start_rebuild = time.time()

    # Store callback for later use by maybe_rebuild_tfidf
    if reindex_callback:
        _reindex_callback = reindex_callback

    # Skip rebuild if model exists and force=False
    if not force and os.path.exists(TFIDF_MODEL_PATH):
        # Check if model is recent enough
        model_mtime = os.path.getmtime(TFIDF_MODEL_PATH)
        # If model was built in the last hour, skip
        if time.time() - model_mtime < 3600:
            _load_tfidf_model()
            end_rebuild = time.time()
            print(f"Total rebuild time: {(end_rebuild - start_rebuild)*1000:.2f} ms")
            return _tfidf_vectorizer

    files = _get_git_files()
    if not files:
        end_rebuild = time.time()
        print(f"Total rebuild time: {(end_rebuild - start_rebuild)*1000:.2f} ms")
        return None

    documents = []
    file_paths = []
    for fpath in files:
        if os.path.exists(fpath):
            try:
                content = open(fpath).read()
                documents.append(content)
                file_paths.append(fpath)
            except:
                pass

    if not documents:
        return None

    # Don't use English stop words - code often uses words like 'file', 'function', 'class', etc.
    vectorizer = TfidfVectorizer(max_features=1000, stop_words=None, token_pattern=r'\b\w+\b')
    start_fit = time.time()
    vectorizer.fit(documents)
    end_fit = time.time()
    print(f"Fit time: {(end_fit - start_fit)*1000:.2f} ms")
    _save_tfidf_model(vectorizer)

    # Re-index all files with TF-IDF keywords if callback provided
    # Note: This happens during initial startup, so it's acceptable to be slower
    # The callback (index_file) already batches operations per file
    callback = reindex_callback or _reindex_callback
    if callback:
        for fpath in file_paths:
            callback(fpath)

    # Reset counter after rebuild
    _files_changed_since_rebuild = 0

    end_rebuild = time.time()
    print(f"Total rebuild time: {(end_rebuild - start_rebuild)*1000:.2f} ms")

    return vectorizer

def maybe_rebuild_tfidf():
    """Conditionally rebuild TF-IDF model based on file change threshold.

    Uses the stored reindex callback from the last rebuild_tfidf_model() call.
    """
    global _files_changed_since_rebuild

    _files_changed_since_rebuild += 1

    if _files_changed_since_rebuild >= _rebuild_threshold:
        # Use stored callback, no need to pass it again
        rebuild_tfidf_model(force=True)
        _files_changed_since_rebuild = 0

def extract_top_keywords(text, n=None, context='default'):
    """
    Extract top N keywords from text using TF-IDF with smart defaults.

    Args:
        text: Text to extract keywords from
        n: Number of keywords (None = auto-select based on context)
        context: Context hint for smart defaults:
            - 'file': extracting from file content (default: 10)
            - 'prompt': extracting from user prompt (default: 10)
            - 'default': general use (default: 5)

    Returns:
        List of keywords
    """
    # Smart defaults based on context
    if n is None:
        if context == 'file':
            n = 10  # More keywords for indexing files
        elif context == 'prompt':
            n = 10  # More keywords for user queries
        else:
            n = 5   # Conservative default for general use

    vectorizer = _load_tfidf_model()
    if vectorizer is None:
        # Fallback to simple word extraction if model not available
        words = re.findall(r'\b\w+\b', text.lower())
        return list(set(words))[:n]

    try:
        tfidf_matrix = vectorizer.transform([text])
        feature_names = vectorizer.get_feature_names_out()
        scores = tfidf_matrix.toarray()[0]

        # Get indices of top N scores
        top_indices = np.argsort(scores)[::-1][:n]
        keywords = [feature_names[i] for i in top_indices if scores[i] > 0]

        return keywords if keywords else list(set(re.findall(r'\b\w+\b', text.lower())))[:n]
    except:
        # Fallback if TF-IDF fails
        words = re.findall(r'\b\w+\b', text.lower())
        return list(set(words))[:n]
