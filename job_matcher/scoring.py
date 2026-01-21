from sklearn.metrics.pairwise import cosine_similarity




def compute_score(required, preferred, resume_skills):
    req = len(required & resume_skills) / max(len(required), 1)
    pref = len(preferred & resume_skills) / max(len(preferred), 1)
    return req, pref