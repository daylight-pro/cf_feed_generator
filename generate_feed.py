from dataclasses import dataclass
import time
from enum import Enum
import requests
import json
import hashlib
import random

with open("settings.json") as f:
    settings = json.load(f)

api_key = settings["api_key"]
api_secret = settings["api_secret"]

contest_id = settings["contest_id"]
group_code = settings["group_code"] if "group_code" in settings.keys() else None

if group_code == "":
    group_code = None

as_manager = settings["as_manager"]


def to_relativetime(seconds):
    """Convert seconds to a string in the format HH:MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}.000"


def to_time(seconds):
    """Convert seconds to a string in the format YYYY-MM-DDTHH:MM:SS."""
    return time.strftime("%Y-%m-%dT%H:%M:%S.000+09:00", time.gmtime(seconds))


class Problem:
    __id = 1
    __problem_list = {}
    index: str

    def __init__(self, data: dict):
        self.index = data["index"]
        if self.index not in Problem.__problem_list.keys():
            Problem.__problem_list[self.index] = Problem.__id
            Problem.__id += 1

    def getId(self):
        return Problem.__problem_list[self.index]


class Member:
    handle: str

    def __init__(self, data):
        self.handle = data["handle"]


class Party:
    __id = 1
    __party_dict = {}
    members: list
    teamName: str

    def __init__(self, data: dict):
        self.members = []
        for member in data["members"]:
            self.members.append(Member(member))
        self.teamName = (
            data["teamName"] if "teamName" in data else data["members"][0]["handle"]
        )
        if self.getName() not in Party.__party_dict.keys():
            Party.__party_dict[self.getName()] = Party.__id
            Party.__id += 1

    def getName(self):
        if self.teamName:
            return self.teamName
        else:
            return " ".join(map(lambda x: x.handle, self.members))

    def getId(self):
        return Party.__party_dict[self.getName()]


class Verdict(Enum):
    IGNORE = -1
    AC = 1
    CE = 2
    IC = 3

    def __str__(self):
        return "AC" if self == Verdict.AC else "CE" if self == Verdict.CE else "IC"

    def __from_string__(value: str):
        if value == "OK":
            return Verdict.AC
        elif value == "COMPILATION_ERROR":
            return Verdict.CE
        elif (
            value == "FAILED"
            or value == "CRASHED"
            or value == "INPUT_PREPARATION_CRASHED"
            or value == "SUBMITTED"
            or value == "REJECTED"
            or value == "TESTING"
            or value == "SKIPPED"
        ):
            return Verdict.IGNORE
        else:
            return Verdict.IC


class Submission:
    id: int
    creationTimeSeconds: int
    relativeTimeSeconds: int
    problem: Problem
    author: Party
    verdict: Verdict

    def __init__(self, data: dict):
        self.id = data["id"]
        self.creationTimeSeconds = data["creationTimeSeconds"]
        self.relativeTimeSeconds = data["relativeTimeSeconds"]
        self.problem = Problem(data["problem"])
        self.author = Party(data["author"])
        self.verdict = Verdict.__from_string__(data["verdict"])


class Contest:
    startTimeSeconds: int
    durationSeconds: int
    freezeDurationSeconds: int
    name: str

    def __init__(self, data: dict):
        self.startTimeSeconds = data["startTimeSeconds"]
        self.durationSeconds = data["durationSeconds"]
        self.freezeDurationSeconds = data["freezeDurationSeconds"]
        self.name = data["name"]


class Award:
    id: str
    citation: str
    teamIds: list

    def __init__(self, data: dict):
        self.id = data["id"]
        self.citation = data["citation"]
        self.teamIds = data["teamIds"]


class Feed:
    def __init__(self, id, type, data):
        self.id = id
        self.type = type
        self.data = data

    def generate_feeds(self):
        return [{"id": self.id, "type": self.type, "data": self.data}]


class ContestFeed(Feed):
    def __init__(self, data: Contest):
        self.data = data
        self.id = None

    def generate_feeds(self):
        contest = self.data
        return [
            {
                "id": None,
                "type": "contest",
                "data": {
                    "formal_name": contest.name,
                    "start_time": to_time(contest.startTimeSeconds),
                    "end_time": to_time(
                        contest.startTimeSeconds + contest.durationSeconds
                    ),
                    "duration": to_relativetime(contest.durationSeconds),
                    "scoreboard_freeze_duration": to_relativetime(
                        contest.freezeDurationSeconds
                    ),
                    "id": contest_id,
                    "penalty_time": "20",
                    "name": contest.name,
                },
            }
        ]


class ProblemFeed(Feed):
    def __init__(self, data: Problem):
        self.data = data
        self.id = self.data.getId()

    def generate_feeds(self):
        problem = self.data
        return [
            {
                "id": str(problem.getId()),
                "type": "problems",
                "data": {
                    "short_name": problem.index,
                    "label": problem.index,
                    "id": str(problem.getId()),
                    "ordinal": str(problem.getId() - 1),
                    "penalty_time": 20,
                },
            }
        ]


class TeamFeed(Feed):
    def __init__(self, data: Party):
        self.data = data
        self.id = self.data.getId()

    def generate_feeds(self):
        team = self.data
        return [
            {
                "id": str(team.getId()),
                "type": "teams",
                "data": {
                    "hidden": False,
                    "id": str(team.getId()),
                    "name": team.getName(),
                },
            }
        ]


class SubmissionFeed(Feed):
    def __init__(self, data: Submission):
        self.data = data
        self.id = self.data.id

    def generate_feeds(self):
        submission = self.data
        return [
            {
                "id": str(submission.id),
                "type": "submissions",
                "data": {
                    "time": to_time(submission.creationTimeSeconds),
                    "contest_time": to_relativetime(submission.relativeTimeSeconds),
                    "team_id": str(submission.author.getId()),
                    "problem_id": str(submission.problem.getId()),
                    "id": str(submission.id),
                },
            },
            {
                "id": str(submission.id),
                "type": "judgements",
                "data": {
                    "start_time": to_time(submission.creationTimeSeconds),
                    "start_contest_time": to_relativetime(
                        submission.relativeTimeSeconds
                    ),
                    "end_time": to_time(submission.creationTimeSeconds),
                    "end_contest_time": to_relativetime(submission.relativeTimeSeconds),
                    "submission_id": str(submission.id),
                    "id": str(submission.id),
                    "valid": True,
                    "judgement_type_id": str(submission.verdict),
                },
            },
        ]


class AwardFeed(Feed):
    def __init__(self, data: Award):
        self.data = data

    def generate_feeds(self):
        return [
            {
                "id": self.data.id,
                "type": "awards",
                "data": {
                    "id": self.data.id,
                    "team_ids": self.data.teamIds,
                    "citation": self.data.citation,
                },
            }
        ]


feeds = []
FA = {}
solved = set()

participants = set()

rand = random.randint(0, 100000)
rand = str(rand).zfill(6)
current_time = str(int(time.time()))
api_sig = (
    rand
    + "/contest.standings?apiKey="
    + api_key
    + "&asManager="
    + str(as_manager)
    + "&contestId="
    + contest_id
    + f"{'' if group_code is None else '&groupCode=' + group_code}"
    + "&time="
    + current_time
    + "#"
    + api_secret
)
hash = hashlib.sha512(api_sig.encode()).hexdigest()
data = requests.get(
    f"https://codeforces.com/api/contest.standings?asManager={as_manager}"
    + f"{'' if group_code is None else f'&groupCode={group_code}'}"
    + f"&contestId={contest_id}&apiKey={api_key}&time={current_time}&apiSig={rand+hash}"
).json()

contest = Contest(data["result"]["contest"])
feeds.extend(ContestFeed(contest).generate_feeds())

feeds.extend(
    Feed(
        "AC",
        "judgement-types",
        {"id": "AC", "name": "correct", "penalty": False, "solved": True},
    ).generate_feeds()
)

feeds.extend(
    Feed(
        "CE",
        "judgement-types",
        {"id": "CE", "name": "compiler error", "penalty": False, "solved": False},
    ).generate_feeds()
)

feeds.extend(
    Feed(
        "IC",
        "judgement-types",
        {"id": "IC", "name": "incorrect", "penalty": True, "solved": False},
    ).generate_feeds()
)

for problem in data["result"]["problems"]:
    problem_data = Problem(problem)
    feeds.extend(ProblemFeed(problem_data).generate_feeds())

for participant in data["result"]["rows"]:
    participant_data = Party(participant["party"])
    participants.add(participant_data.getId())
    feeds.extend(TeamFeed(participant_data).generate_feeds())
    feeds.extend(
        AwardFeed(
            Award(
                {
                    "id": "winner",
                    "teamIds": [str(participant_data.getId())],
                    "citation": "Contest Winner",
                }
            )
        ).generate_feeds()
    )

rand = random.randint(0, 100000)
rand = str(rand).zfill(6)
current_time = str(int(time.time()))
api_sig = (
    rand
    + "/contest.status?apiKey="
    + api_key
    + "&asManager="
    + str(as_manager)
    + "&contestId="
    + contest_id
    + f"{'' if group_code is None else '&groupCode=' + group_code}"
    + "&time="
    + current_time
    + "#"
    + api_secret
)
hash = hashlib.sha512(api_sig.encode()).hexdigest()
data = requests.get(
    f"https://codeforces.com/api/contest.status?asManager={as_manager}"
    + f"{'' if group_code is None else f'&groupCode={group_code}'}"
    + f"&contestId={contest_id}&apiKey={api_key}&time={current_time}&apiSig={rand+hash}"
).json()


for status in data["result"]:
    status_data = Submission(status)
    if status_data.author.getId() not in participants:
        continue
    feeds.extend(SubmissionFeed(status_data).generate_feeds())
    if status_data.verdict == Verdict.AC:
        if status_data.problem.index in solved:
            continue
        solved.add(status_data.problem.index)
        if status_data.author.getId() not in FA.keys():
            FA[status_data.author.getId()] = list()
        FA[status_data.author.getId()].append(status_data.problem.index)

for i, team_id in enumerate(FA.keys()):
    FA[team_id].sort()
    feeds.extend(
        AwardFeed(
            Award(
                {
                    "id": f"first_to_solve_{i}",
                    "teamIds": [str(team_id)],
                    "citation": f"First to solve problem {', '.join(FA[team_id])}",
                }
            )
        ).generate_feeds()
    )


feeds.extend(
    Feed(
        None,
        "state",
        {
            "started": to_time(contest.startTimeSeconds),
            "ended": to_time(contest.startTimeSeconds + contest.durationSeconds),
            "frozen": to_time(contest.startTimeSeconds + contest.freezeDurationSeconds),
            "finalized": to_time(contest.startTimeSeconds + contest.durationSeconds),
            "end_of_updates": to_time(
                contest.startTimeSeconds + contest.durationSeconds
            ),
        },
    ).generate_feeds()
)

for feed in feeds:
    print(json.dumps(feed, ensure_ascii=False))
