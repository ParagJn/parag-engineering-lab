#!/usr/bin/env python3
"""TalentFlow API Backend — CGI script for candidate search, JD parsing, outreach, and pipeline."""

import json
import os
import sys
import re
import hashlib
import random
import sqlite3
from urllib.parse import parse_qs

# --- Database Setup ---
DB_PATH = "talentflow_pipeline.db"

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS pipeline (
        id TEXT PRIMARY KEY,
        candidate_data TEXT,
        stage TEXT DEFAULT 'sourced',
        notes TEXT DEFAULT '',
        tags TEXT DEFAULT '[]',
        outreach_history TEXT DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    db.commit()
    return db

def respond(data, status=200):
    print(f"Status: {status}")
    print("Content-Type: application/json")
    print()
    print(json.dumps(data))
    sys.exit(0)

def read_body():
    length = int(os.environ.get("CONTENT_LENGTH", 0))
    if length > 0:
        return json.loads(sys.stdin.read(length))
    return {}

# --- JD Parsing Logic ---
SKILL_KEYWORDS = {
    "python": "Python", "java": "Java", "javascript": "JavaScript", "typescript": "TypeScript",
    "react": "React", "angular": "Angular", "vue": "Vue.js", "node": "Node.js", "nodejs": "Node.js",
    "go": "Go", "golang": "Go", "rust": "Rust", "c++": "C++", "cpp": "C++",
    "ruby": "Ruby", "rails": "Ruby on Rails", "django": "Django", "flask": "Flask",
    "aws": "AWS", "gcp": "GCP", "azure": "Azure", "docker": "Docker", "kubernetes": "Kubernetes",
    "k8s": "Kubernetes", "terraform": "Terraform", "ci/cd": "CI/CD", "cicd": "CI/CD",
    "sql": "SQL", "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mysql": "MySQL",
    "mongodb": "MongoDB", "redis": "Redis", "elasticsearch": "Elasticsearch",
    "graphql": "GraphQL", "rest": "REST APIs", "api": "API Design",
    "machine learning": "Machine Learning", "ml": "Machine Learning", "ai": "AI/ML",
    "deep learning": "Deep Learning", "nlp": "NLP", "computer vision": "Computer Vision",
    "tensorflow": "TensorFlow", "pytorch": "PyTorch", "pandas": "Pandas", "numpy": "NumPy",
    "spark": "Apache Spark", "kafka": "Apache Kafka", "airflow": "Apache Airflow",
    "figma": "Figma", "sketch": "Sketch", "adobe": "Adobe Creative Suite",
    "html": "HTML/CSS", "css": "HTML/CSS", "sass": "Sass/SCSS",
    "tailwind": "Tailwind CSS", "next": "Next.js", "nextjs": "Next.js",
    "svelte": "Svelte", "nuxt": "Nuxt.js",
    "swift": "Swift", "kotlin": "Kotlin", "flutter": "Flutter", "react native": "React Native",
    "linux": "Linux", "unix": "Unix/Linux",
    "agile": "Agile", "scrum": "Scrum", "jira": "Jira",
    "git": "Git", "github": "GitHub",
    "microservices": "Microservices", "distributed systems": "Distributed Systems",
    "system design": "System Design", "data structures": "Data Structures",
    "security": "Security", "cybersecurity": "Cybersecurity",
    "devops": "DevOps", "sre": "SRE", "site reliability": "SRE",
    "product management": "Product Management", "product design": "Product Design",
    "ux": "UX Design", "ui": "UI Design", "user research": "User Research",
    "data engineering": "Data Engineering", "data science": "Data Science",
    "analytics": "Analytics", "tableau": "Tableau", "power bi": "Power BI",
    "salesforce": "Salesforce", "hubspot": "HubSpot",
    "blockchain": "Blockchain", "web3": "Web3", "solidity": "Solidity",
    "scala": "Scala", "haskell": "Haskell", "elixir": "Elixir", "erlang": "Erlang",
    "php": "PHP", "laravel": "Laravel", "wordpress": "WordPress",
}

SENIORITY_PATTERNS = [
    (r'\b(?:staff|principal|distinguished|fellow)\b', 'Staff/Principal'),
    (r'\b(?:senior|sr\.?|lead|tech lead)\b', 'Senior'),
    (r'\b(?:mid[- ]?level|mid[- ]?senior|intermediate)\b', 'Mid-Level'),
    (r'\b(?:junior|jr\.?|entry[- ]?level|associate|new grad|graduate)\b', 'Junior'),
    (r'\b(?:intern|internship|co-op)\b', 'Intern'),
    (r'\b(?:manager|director|head of|vp|vice president|chief)\b', 'Management'),
]

ROLE_PATTERNS = [
    (r'\b(?:full[- ]?stack|fullstack)\b', 'Full-Stack'),
    (r'\b(?:front[- ]?end|frontend)\b', 'Frontend'),
    (r'\b(?:back[- ]?end|backend)\b', 'Backend'),
    (r'\b(?:mobile|ios|android)\b', 'Mobile'),
    (r'\b(?:devops|infrastructure|platform|sre|site reliability)\b', 'DevOps/Infrastructure'),
    (r'\b(?:data scien|machine learning|ml engineer|ai engineer)\b', 'Data Science/ML'),
    (r'\b(?:data engineer)\b', 'Data Engineering'),
    (r'\b(?:security|cybersecurity|appsec)\b', 'Security'),
    (r'\b(?:product manag)\b', 'Product Management'),
    (r'\b(?:design|ux|ui)\b', 'Design'),
    (r'\b(?:qa|quality|test|sdet)\b', 'QA/Testing'),
    (r'\b(?:cloud|architect)\b', 'Cloud/Architecture'),
]

LOCATION_PATTERNS = [
    r'(?:based in|located in|location:?\s*)([\w\s,]+)',
    r'((?:San Francisco|New York|Seattle|Austin|Chicago|Boston|Denver|Portland|Los Angeles|Miami|Atlanta|Dallas|Remote|Hybrid)(?:\s*,\s*\w+)?)',
    r'(remote|hybrid|on[- ]?site|in[- ]?office)',
]

YOE_PATTERNS = [
    r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)',
    r'(\d+)-(\d+)\s*(?:years?|yrs?)',
    r'(?:experience|exp):?\s*(\d+)\+?\s*(?:years?|yrs?)',
    r'(?:minimum|at least|min)\s*(\d+)\s*(?:years?|yrs?)',
]

def parse_jd(text):
    lower = text.lower()
    
    # Extract skills
    found_skills = set()
    for keyword, skill_name in SKILL_KEYWORDS.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', lower):
            found_skills.add(skill_name)
    
    # Extract seniority
    seniority = 'Mid-Level'
    for pattern, level in SENIORITY_PATTERNS:
        if re.search(pattern, lower):
            seniority = level
            break
    
    # Extract role type
    role_type = 'Software Engineering'
    for pattern, role in ROLE_PATTERNS:
        if re.search(pattern, lower):
            role_type = role
            break
    
    # Extract location
    locations = []
    for pattern in LOCATION_PATTERNS:
        matches = re.findall(pattern, lower, re.IGNORECASE)
        for m in matches:
            loc = m.strip().title() if isinstance(m, str) else m[0].strip().title()
            if loc and len(loc) > 2:
                locations.append(loc)
    if not locations:
        locations = ['Remote']
    
    # Extract years of experience
    yoe_min, yoe_max = 3, 7
    for pattern in YOE_PATTERNS:
        m = re.search(pattern, lower)
        if m:
            groups = m.groups()
            if len(groups) == 2 and groups[1]:
                yoe_min = int(groups[0])
                yoe_max = int(groups[1])
            else:
                yoe_min = int(groups[0])
                yoe_max = yoe_min + 4
            break
    
    # Infer from seniority if not found
    if seniority == 'Junior':
        yoe_min, yoe_max = 0, 3
    elif seniority == 'Senior':
        yoe_min, yoe_max = max(yoe_min, 5), max(yoe_max, 10)
    elif seniority == 'Staff/Principal':
        yoe_min, yoe_max = max(yoe_min, 8), max(yoe_max, 15)
    elif seniority == 'Management':
        yoe_min, yoe_max = max(yoe_min, 7), max(yoe_max, 15)
    
    # Extract education
    education = 'Not specified'
    if re.search(r'\b(?:phd|doctorate|ph\.d)\b', lower):
        education = 'PhD preferred'
    elif re.search(r'\b(?:master|ms|msc|m\.s\.)\b', lower):
        education = "Master's preferred"
    elif re.search(r'\b(?:bachelor|bs|bsc|b\.s\.|degree)\b', lower):
        education = "Bachelor's required"
    
    # Extract salary if mentioned
    salary = None
    sal_match = re.search(r'\$\s*([\d,]+)(?:k|\s*,?\s*000)?(?:\s*[-–]\s*\$?\s*([\d,]+)(?:k|\s*,?\s*000)?)?', lower)
    if sal_match:
        lo = sal_match.group(1).replace(',', '')
        salary = f"${lo}k"
        if sal_match.group(2):
            hi = sal_match.group(2).replace(',', '')
            salary = f"${lo}k - ${hi}k"

    if not found_skills:
        found_skills = {'Python', 'JavaScript', 'SQL'}
    
    return {
        "skills": sorted(list(found_skills)),
        "seniority": seniority,
        "role_type": role_type,
        "locations": list(set(locations)),
        "yoe_range": [yoe_min, yoe_max],
        "education": education,
        "salary_range": salary,
        "raw_length": len(text),
    }

# --- Candidate Generation ---
FIRST_NAMES = ["Alex", "Jordan", "Morgan", "Taylor", "Casey", "Riley", "Quinn", "Avery",
               "Priya", "Wei", "Carlos", "Aisha", "Soren", "Maya", "Kenji", "Elena",
               "Dmitri", "Fatima", "Liam", "Zara", "Raj", "Sophie", "Marcus", "Yuki",
               "Amara", "Lucas", "Nina", "Omar", "Clara", "Jin"]

LAST_NAMES = ["Chen", "Williams", "Patel", "Mueller", "Garcia", "Kim", "Johnson", "Singh",
              "Anderson", "Martinez", "Lee", "Thompson", "Nakamura", "Robinson", "Okafor",
              "Johansson", "Dubois", "Santos", "Nguyen", "Foster", "Rivera", "Tanaka",
              "Schmidt", "Costa", "Ali", "Brooks", "Volkov", "Park", "Wright", "Huang"]

COMPANIES = [
    {"name": "Google", "tier": "FAANG"}, {"name": "Meta", "tier": "FAANG"},
    {"name": "Apple", "tier": "FAANG"}, {"name": "Amazon", "tier": "FAANG"},
    {"name": "Microsoft", "tier": "FAANG"}, {"name": "Netflix", "tier": "FAANG"},
    {"name": "Stripe", "tier": "Top Startup"}, {"name": "Figma", "tier": "Top Startup"},
    {"name": "Vercel", "tier": "Top Startup"}, {"name": "Datadog", "tier": "Top Startup"},
    {"name": "Snowflake", "tier": "Top Startup"}, {"name": "Databricks", "tier": "Top Startup"},
    {"name": "Airbnb", "tier": "Top Tech"}, {"name": "Uber", "tier": "Top Tech"},
    {"name": "Shopify", "tier": "Top Tech"}, {"name": "Square", "tier": "Top Tech"},
    {"name": "Twilio", "tier": "Top Tech"}, {"name": "Cloudflare", "tier": "Top Tech"},
    {"name": "Palantir", "tier": "Top Tech"}, {"name": "Confluent", "tier": "Top Tech"},
    {"name": "HashiCorp", "tier": "Top Tech"}, {"name": "Elastic", "tier": "Top Tech"},
    {"name": "MongoDB Inc.", "tier": "Top Tech"}, {"name": "GitLab", "tier": "Top Tech"},
    {"name": "Notion", "tier": "Top Startup"}, {"name": "Linear", "tier": "Top Startup"},
    {"name": "Anthropic", "tier": "AI"}, {"name": "OpenAI", "tier": "AI"},
    {"name": "Cohere", "tier": "AI"}, {"name": "Scale AI", "tier": "AI"},
]

UNIVERSITIES = [
    "MIT", "Stanford", "UC Berkeley", "Carnegie Mellon", "Georgia Tech",
    "University of Washington", "Caltech", "Princeton", "Columbia",
    "University of Michigan", "Cornell", "UCLA", "UT Austin",
    "University of Illinois", "ETH Zurich", "University of Toronto",
    "IIT Delhi", "Tsinghua University", "NUS", "Oxford",
]

LOCATIONS = [
    "San Francisco, CA", "New York, NY", "Seattle, WA", "Austin, TX",
    "Boston, MA", "Chicago, IL", "Denver, CO", "Portland, OR",
    "Los Angeles, CA", "Miami, FL", "Atlanta, GA", "Dallas, TX",
    "London, UK", "Berlin, Germany", "Toronto, Canada", "Remote",
]

def generate_candidates(parsed_jd, filters=None, count=12):
    """Generate realistic candidates based on parsed JD."""
    skills = parsed_jd.get("skills", [])
    seniority = parsed_jd.get("seniority", "Mid-Level")
    role_type = parsed_jd.get("role_type", "Software Engineering")
    yoe_range = parsed_jd.get("yoe_range", [3, 7])
    jd_locations = parsed_jd.get("locations", ["Remote"])
    
    # Create a seed from the JD for consistent results
    seed_str = json.dumps(parsed_jd, sort_keys=True)
    seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    
    candidates = []
    for i in range(count):
        # Name
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        
        # Relevance — first candidates are best matches
        base_score = max(50, 100 - (i * 4) + rng.randint(-5, 5))
        relevance = min(99, max(42, base_score))
        
        # Skills — top candidates have more matching skills
        num_matching = max(1, len(skills) - i // 2)
        matching_skills = rng.sample(skills, min(num_matching, len(skills)))
        
        # Add some extra skills not in JD
        extra_pool = [s for s in ["Git", "Agile", "Linux", "Docker", "REST APIs", "CI/CD", "System Design"] if s not in skills]
        extra_skills = rng.sample(extra_pool, min(rng.randint(1, 3), len(extra_pool)))
        all_skills = list(set(matching_skills + extra_skills))
        
        # YOE
        yoe = rng.randint(max(0, yoe_range[0] - 2), yoe_range[1] + 3)
        
        # Company
        company = rng.choice(COMPANIES)
        
        # Location — prefer JD locations
        if rng.random() < 0.4 and jd_locations:
            loc_raw = rng.choice(jd_locations)
            location = loc_raw if ',' in loc_raw else rng.choice(LOCATIONS)
        else:
            location = rng.choice(LOCATIONS)
        
        # Title
        title_prefixes = {
            "Junior": ["Junior", "Associate"],
            "Mid-Level": ["", ""],
            "Senior": ["Senior", "Staff", "Lead"],
            "Staff/Principal": ["Staff", "Principal", "Distinguished"],
            "Management": ["Engineering Manager", "Director of Engineering", "VP Engineering", "Head of"],
            "Intern": ["Intern"],
        }
        prefix_list = title_prefixes.get(seniority, [""])
        prefix = rng.choice(prefix_list)
        
        role_titles = {
            "Full-Stack": "Full-Stack Engineer",
            "Frontend": "Frontend Engineer",
            "Backend": "Backend Engineer",
            "Mobile": "Mobile Engineer",
            "DevOps/Infrastructure": "Infrastructure Engineer",
            "Data Science/ML": "ML Engineer",
            "Data Engineering": "Data Engineer",
            "Security": "Security Engineer",
            "Product Management": "Product Manager",
            "Design": "Product Designer",
            "QA/Testing": "QA Engineer",
            "Cloud/Architecture": "Cloud Architect",
            "Software Engineering": "Software Engineer",
        }
        base_title = role_titles.get(role_type, "Software Engineer")
        title = f"{prefix} {base_title}".strip() if prefix else base_title
        
        # Headline
        headline = f"{title} at {company['name']}"
        
        # University
        university = rng.choice(UNIVERSITIES)
        degree = rng.choice(["B.S.", "M.S.", "B.S.", "B.S.", "M.S.", "Ph.D."])
        major = rng.choice(["Computer Science", "Software Engineering", "Electrical Engineering", "Mathematics", "Data Science", "Information Systems"])
        
        # Tenure at current company
        tenure_months = rng.randint(6, min(yoe * 12, 60))
        tenure_years = tenure_months / 12
        
        # Career trajectory
        if yoe <= 3:
            trajectory = "Early Career"
        elif yoe <= 6:
            trajectory = "Growth Phase"
        elif yoe <= 10:
            trajectory = "Established"
        else:
            trajectory = "Industry Veteran"
        
        # Open to work
        open_to_work = rng.random() < 0.35
        
        # GitHub presence
        has_github = rng.random() < 0.6
        github_data = None
        if has_github:
            github_data = {
                "repos": rng.randint(5, 120),
                "contributions": rng.randint(100, 3000),
                "stars": rng.randint(0, 500),
                "languages": rng.sample(["Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C++"], rng.randint(2, 5)),
                "activity_score": rng.randint(40, 98),
            }
        
        # Create username-like IDs
        username = f"{first.lower()}{last.lower()}"
        linkedin_url = f"https://linkedin.com/in/{username}"
        github_url = f"https://github.com/{username}" if has_github else None
        
        candidate = {
            "id": hashlib.md5(f"{first}{last}{i}{seed}".encode()).hexdigest()[:12],
            "name": f"{first} {last}",
            "initials": f"{first[0]}{last[0]}",
            "title": title,
            "headline": headline,
            "company": company["name"],
            "company_tier": company["tier"],
            "location": location,
            "yoe": yoe,
            "relevance_score": relevance,
            "skills": all_skills,
            "matching_skills": matching_skills,
            "linkedin_url": linkedin_url,
            "github_url": github_url,
            "github_data": github_data,
            "university": university,
            "degree": f"{degree} {major}",
            "tenure_months": tenure_months,
            "tenure_display": f"{tenure_years:.1f} yrs" if tenure_years >= 1 else f"{tenure_months} mo",
            "trajectory": trajectory,
            "open_to_work": open_to_work,
            "avatar_color": f"hsl({(hash(first + last) % 360)}, 55%, 50%)",
        }
        candidates.append(candidate)
    
    # Apply filters
    if filters:
        if filters.get("min_yoe") is not None:
            candidates = [c for c in candidates if c["yoe"] >= filters["min_yoe"]]
        if filters.get("max_yoe") is not None:
            candidates = [c for c in candidates if c["yoe"] <= filters["max_yoe"]]
        if filters.get("location") and filters["location"] != "all":
            loc_filter = filters["location"].lower()
            candidates = [c for c in candidates if loc_filter in c["location"].lower()]
        if filters.get("skills") and len(filters["skills"]) > 0:
            filter_skills = set(s.lower() for s in filters["skills"])
            candidates = [c for c in candidates if any(s.lower() in filter_skills for s in c["skills"])]
        if filters.get("open_to_work"):
            candidates = [c for c in candidates if c["open_to_work"]]
    
    # Sort by relevance
    candidates.sort(key=lambda c: c["relevance_score"], reverse=True)
    
    return candidates

# --- Outreach Generation ---
def generate_outreach(candidate, jd_text="", tone="professional", length="medium", msg_type="email"):
    name = candidate.get("name", "there")
    first_name = name.split()[0]
    company = candidate.get("company", "your company")
    title = candidate.get("title", "your role")
    skills = candidate.get("matching_skills", candidate.get("skills", []))[:3]
    skills_str = ", ".join(skills) if skills else "your technical background"
    
    tone_adj = {
        "casual": {"greeting": f"Hey {first_name}", "closing": "Cheers", "style": "conversational"},
        "professional": {"greeting": f"Hi {first_name}", "closing": "Best regards", "style": "professional"},
        "formal": {"greeting": f"Dear {name}", "closing": "Sincerely", "style": "formal"},
    }
    t = tone_adj.get(tone, tone_adj["professional"])
    
    if length == "short":
        body_lines = 2
    elif length == "long":
        body_lines = 6
    else:
        body_lines = 4
    
    # Initial email
    if msg_type == "email":
        subject = f"Exciting opportunity — {title} role"
        if tone == "casual":
            subject = f"Quick question about your next move"
        elif tone == "formal":
            subject = f"Re: {title} Opportunity"
        
        bodies = {
            "short": f"""{t['greeting']},

I came across your profile and was impressed by your work at {company}, particularly your expertise in {skills_str}. We have an opening that could be a great fit.

Would you be open to a quick chat this week?

{t['closing']}""",
            "medium": f"""{t['greeting']},

I came across your profile and was immediately impressed by your experience as {title} at {company}. Your background in {skills_str} really stood out.

We're building something exciting and are looking for someone with exactly your skill set. The role offers the chance to work on challenging problems with a talented team, competitive compensation, and strong growth potential.

I'd love to share more details. Would you be open to a brief conversation this week?

{t['closing']}""",
            "long": f"""{t['greeting']},

I hope this message finds you well. I've been following the impressive work being done at {company}, and your contributions as {title} particularly caught my attention.

Your expertise in {skills_str} aligns perfectly with what we're looking for. We're building a world-class engineering team and believe your background would be an incredible addition.

The role offers:
- Challenging technical problems at scale
- A collaborative, high-caliber team
- Competitive compensation and equity
- Flexibility in work arrangements

I've done my homework on your background and genuinely believe this could be a meaningful career opportunity. I'd love to share more details about the role and our technical vision.

Would you have 15-20 minutes this week for a casual conversation? No pressure — I'm happy to share more details over email if you prefer.

{t['closing']}""",
        }
        body = bodies.get(length, bodies["medium"])
    else:
        # InMail style — shorter
        subject = f"Great fit for a {title} role"
        body = f"""{t['greeting']},

Your work at {company} caught my eye — especially your {skills_str} experience. We have a role I think you'd find exciting.

Open to hearing more?

{t['closing']}"""
    
    # Follow-ups
    followup1 = f"""{t['greeting']},

Just following up on my previous message. I know things get busy, but I wanted to make sure this didn't slip through the cracks.

We're still very interested in connecting with you about this opportunity. The team is growing quickly and we'd love to have you be part of it.

Would any time this week work for a brief chat?

{t['closing']}"""
    
    followup2 = f"""{t['greeting']},

I wanted to reach out one more time regarding the {title} opportunity I mentioned. I completely understand if the timing isn't right — these things rarely are.

If you're not looking right now, I'd still love to stay connected for the future. And if you know anyone in your network who might be interested, I'd appreciate any introductions.

Either way, wishing you all the best at {company}.

{t['closing']}"""
    
    return {
        "subject": subject,
        "body": body,
        "followup_1": followup1,
        "followup_2": followup2,
        "type": msg_type,
        "tone": tone,
        "length": length,
        "candidate_name": name,
    }

# --- Route Handler ---
def main():
    method = os.environ.get("REQUEST_METHOD", "GET")
    path_info = os.environ.get("PATH_INFO", "")
    query_string = os.environ.get("QUERY_STRING", "")
    
    # Route: Parse JD
    if path_info == "/parse-jd" and method == "POST":
        body = read_body()
        jd_text = body.get("jd", "")
        if not jd_text.strip():
            respond({"error": "Job description is required"}, 400)
        result = parse_jd(jd_text)
        respond(result)
    
    # Route: Search Candidates
    elif path_info == "/search" and method == "POST":
        body = read_body()
        parsed_jd = body.get("parsed_jd", {})
        filters = body.get("filters", {})
        count = body.get("count", 12)
        if not parsed_jd:
            respond({"error": "Parsed JD data is required"}, 400)
        candidates = generate_candidates(parsed_jd, filters, count)
        respond({"candidates": candidates, "total": len(candidates)})
    
    # Route: Draft Outreach
    elif path_info == "/draft-outreach" and method == "POST":
        body = read_body()
        candidate = body.get("candidate", {})
        tone = body.get("tone", "professional")
        length = body.get("length", "medium")
        msg_type = body.get("type", "email")
        jd_text = body.get("jd_text", "")
        if not candidate:
            respond({"error": "Candidate data is required"}, 400)
        result = generate_outreach(candidate, jd_text, tone, length, msg_type)
        respond(result)
    
    # Route: Pipeline
    elif path_info == "/pipeline" and method == "GET":
        db = get_db()
        rows = db.execute("SELECT id, candidate_data, stage, notes, tags, outreach_history, created_at, updated_at FROM pipeline ORDER BY updated_at DESC").fetchall()
        items = []
        for row in rows:
            item = json.loads(row[1])
            item["pipeline_id"] = row[0]
            item["stage"] = row[2]
            item["notes"] = row[3]
            item["tags"] = json.loads(row[4])
            item["outreach_history"] = json.loads(row[5])
            item["pipeline_created"] = row[6]
            item["pipeline_updated"] = row[7]
            items.append(item)
        respond({"pipeline": items})
    
    elif path_info == "/pipeline" and method == "POST":
        body = read_body()
        action = body.get("action", "add")
        db = get_db()
        
        if action == "add":
            candidate = body.get("candidate", {})
            cid = candidate.get("id", hashlib.md5(json.dumps(candidate).encode()).hexdigest()[:12])
            # Check if already exists
            existing = db.execute("SELECT id FROM pipeline WHERE id = ?", [cid]).fetchone()
            if existing:
                respond({"error": "Candidate already in pipeline", "id": cid}, 400)
            db.execute(
                "INSERT INTO pipeline (id, candidate_data, stage) VALUES (?, ?, ?)",
                [cid, json.dumps(candidate), body.get("stage", "sourced")]
            )
            db.commit()
            respond({"success": True, "id": cid, "stage": "sourced"}, 201)
        
        elif action == "move":
            cid = body.get("id")
            new_stage = body.get("stage")
            if not cid or not new_stage:
                respond({"error": "id and stage required"}, 400)
            db.execute(
                "UPDATE pipeline SET stage = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [new_stage, cid]
            )
            db.commit()
            respond({"success": True, "id": cid, "stage": new_stage})
        
        elif action == "update_notes":
            cid = body.get("id")
            notes = body.get("notes", "")
            db.execute(
                "UPDATE pipeline SET notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [notes, cid]
            )
            db.commit()
            respond({"success": True})
        
        elif action == "update_tags":
            cid = body.get("id")
            tags = body.get("tags", [])
            db.execute(
                "UPDATE pipeline SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [json.dumps(tags), cid]
            )
            db.commit()
            respond({"success": True})
        
        elif action == "remove":
            cid = body.get("id")
            db.execute("DELETE FROM pipeline WHERE id = ?", [cid])
            db.commit()
            respond({"success": True})
        
        elif action == "add_outreach":
            cid = body.get("id")
            outreach = body.get("outreach", {})
            row = db.execute("SELECT outreach_history FROM pipeline WHERE id = ?", [cid]).fetchone()
            if row:
                history = json.loads(row[0])
                history.append(outreach)
                db.execute(
                    "UPDATE pipeline SET outreach_history = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    [json.dumps(history), cid]
                )
                db.commit()
            respond({"success": True})
        
        else:
            respond({"error": f"Unknown action: {action}"}, 400)
    
    else:
        respond({"error": "Not found", "path": path_info, "method": method}, 404)

if __name__ == "__main__":
    main()
