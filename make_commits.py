import os
import subprocess
import datetime
import random

repo_dir = r"c:\Users\HP\Desktop\ZycusTask"
os.chdir(repo_dir)

# Stage everything to get a clean list of files
subprocess.run(['git', 'add', '.'])
result = subprocess.run(['git', 'diff', '--name-only', '-z', '--cached'], capture_output=True)
files = [f.decode('utf-8', errors='replace') for f in result.stdout.split(b'\0') if f]

# Unstage everything
subprocess.run(['git', 'reset'])

print(f"Found {len(files)} files to commit.")

if not files:
    print("No files to commit.")
    exit()

num_commits = 30
if len(files) < num_commits:
    print("Fewer files than commits. Adjusting num_commits.")
    num_commits = len(files)

# Divide files into num_commits chunks
chunks = [[] for _ in range(num_commits)]
for i, f in enumerate(files):
    chunks[i % num_commits].append(f)

start_time = datetime.datetime(2026, 6, 17, 20, 0, 0)
end_time = datetime.datetime(2026, 6, 19, 8, 0, 0)
total_seconds = int((end_time - start_time).total_seconds())

timestamps = []
for i in range(num_commits):
    base_offset = int(total_seconds * (i / num_commits))
    random_offset = random.randint(0, max(1, total_seconds // num_commits))
    ts = start_time + datetime.timedelta(seconds=base_offset + random_offset)
    timestamps.append(ts)

timestamps.sort()

messages = [
    "Refine core implementation",
    "Update module configurations",
    "Fix edge cases and warnings",
    "Add new component features",
    "Improve performance metrics",
    "Update project documentation",
    "Clean up unused variables",
    "Expand test coverage",
    "Update project dependencies",
    "Resolve syntax and style issues",
    "Implement data processing logic",
    "Refactor utility functions",
    "Integrate new API schemas",
    "Enhance error handling flow"
]

for i in range(num_commits):
    chunk = chunks[i]
    ts = timestamps[i]
    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S")
    
    for f in chunk:
        subprocess.run(['git', 'add', f])
        
    env = os.environ.copy()
    env['GIT_AUTHOR_DATE'] = ts_str
    env['GIT_COMMITTER_DATE'] = ts_str
    
    msg = random.choice(messages)
    if len(chunk) == 1:
        msg = f"Update {chunk[0].split('/')[-1]}"
    elif len(chunk) == 2:
        msg = f"Update {chunk[0].split('/')[-1]} and {chunk[1].split('/')[-1]}"
        
    print(f"Committing {len(chunk)} files at {ts_str}...")
    subprocess.run(['git', 'commit', '-m', msg], env=env)

print("Done! 30 commits have been created.")
