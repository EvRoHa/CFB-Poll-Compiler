import csv
import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup as bs
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class Poll(object):
    headers = {'User-Agent': 'Mozilla/5.0'}

    def __init__(self, year=2018, week=1):
        self.ballots = {}
        self.year = year
        self.date = None
        if week in range(1, 16):
            self.week = week
        else:
            self.week = 1

    def flatten(self):
        out = []
        for v in self.ballots['voters']:
            i = 1
            for t in self.ballots['voters'][v]:
                if self.date:
                    out.append([self.date.strftime('%x'), v, i, t])
                i += 1
        return out

    def flat_csv(self, file=None):
        result = self.flatten()
        with open(file, 'w+', newline='') as outfile:
            csvwriter = csv.writer(outfile)
            csvwriter.writerow(['date', 'voter', 'rank', 'team'])
            for row in result:
                csvwriter.writerow(row)

    def json_out(self, file=None):
        with open(file, 'w+') as outfile:
            json.dump(self.ballots, outfile, indent=4, sort_keys=True)

    def scrape(self, url=None, retries=10):
        # Local solution to retrying after timeout or errors
        def requests_retry_session(retries=retries, backoff_factor=0.3, status_forcelist=(500, 502, 504), session=None):
            session = session or requests.Session()
            retry = Retry(
                total=retries,
                read=retries,
                connect=retries,
                backoff_factor=backoff_factor,
                status_forcelist=status_forcelist,
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            return session

        return requests_retry_session().get(url)

    def table_csv(self, file=None, transpose=False):
        with open(file, 'w+', newline='') as outfile:
            csvwriter = csv.writer(outfile)
            if not transpose:
                csvwriter.writerow(['Rank'] + [x for x in self.ballots['voters']])
                for i in range(0, 25):
                    row = [i + 1]
                    for voter in self.ballots['voters']:
                        row.append(self.ballots['voters'][voter][i])
                    csvwriter.writerow(row)
            else:
                csvwriter.writerow(['Voter'] + [x + 1 for x in range(0, 25)])
                for voter in self.ballots['voters']:
                    csvwriter.writerow([voter] + self.ballots['voters'][voter])


class APPoll(Poll):
    def __init__(self, year=2018, week=1):
        super().__init__(year=year, week=week)
        self.date = None

    def flatten(self):
        out = []
        for v in self.ballots['voters']:
            coach_team = self.ballots['voters'][v]['team']
            for t in self.ballots['voters'][v]['rankings']:
                out.append([self.year, self.week, v, coach_team, t[1], t[0]])
        return out

    def flat_csv(self, file=None):
        if not file:
            file = ' '.join(['Flat', str(self.year), 'Week', str(self.week), 'AP Poll.csv'])

        result = self.flatten()
        with open(file, 'w+', newline='') as outfile:
            csvwriter = csv.writer(outfile)
            csvwriter.writerow(['year', 'week', 'voter', 'coached team', 'rank', 'team'])
            for row in result:
                csvwriter.writerow(row)

    def json_out(self, file=None):
        if not file:
            file = ' '.join([str(self.year), 'Week', str(self.week), 'AP Poll.json'])

        super().json_out(file)

    def scrape(self, url='https://collegefootball.ap.org/poll', timeout=10):
        # the AP records all 2018 seasons as "2019"
        year = self.year
        if year == datetime.now().year:
            year += 1

        url = '/'.join(['https://collegefootball.ap.org/poll', str(year), str(self.week)])

        r = super().scrape(url=url)

        # record the publishing date
        date = bs(r.text, features='html.parser').find('div', {'id': 'poll-released'}).text.split(' ')[-2:]
        self.date = datetime.strptime(' '.join(date), '%b %d')
        if self.date.month < 8:
            self.date = self.date.replace(year=year)
        else:
            self.date = self.date.replace(year=self.year)
        self.ballots['date'] = self.date.strftime('%A %x').replace('/', '-')

        # Find the voter menu
        links = bs(r.text, features='html.parser').find('div', {'class': 'voter-menu filter-menu clearfix'})

        # get the links
        links = links.findAll({'a': 'href'})

        # extract the urls and add the root prefix
        voters = {x.contents[0]: 'https://collegefootball.ap.org/' + x['href'] for x in links}

        self.ballots['voters'] = {}

        for v in voters:
            r = super().scrape(voters[v])

            # Find the ballot table
            table = bs(r.text, features='html.parser').find('table')

            # get the rows
            rows = table.findAll('tr', {'class': re.compile('[0-9]*')})

            # Make a length 25 list
            self.ballots['voters'][v] = ['' for x in range(0, 25)]

            for row in rows:
                rank = int(row.contents[0].text)
                team = row.contents[1].text
                team = re.sub(r'\([^)]*\)', '', team).strip()
                self.ballots['voters'][v][rank - 1] = team

    def table_csv(self, file=None, transpose=False):
        if not file:
            if transpose:
                file = ' '.join([str(self.year), 'Week', str(self.week), 'AP Poll Transposed.csv'])
            else:
                file = ' '.join([str(self.year), 'Week', str(self.week), 'AP Poll.csv'])
        super().table_csv(file=file, transpose=transpose)


class CoachesPoll(Poll):
    def flat_csv(self, file=None):
        if not file:
            file = ' '.join(['Flat', str(self.year), 'Week', str(self.week), 'Coaches Poll.csv'])

        super().flat_csv(file)

    def json_out(self, file=None):
        if not file:
            file = ' '.join([str(self.year), 'Week', str(self.week), 'Coaches Poll.json'])

        super().json_out(file)

    def scrape(self, url='https://www.usatoday.com/sports/ncaaf/ballots/', timeout=10):

        r = super().scrape(url='/'.join([url, 'coaches', self.year.__str__(), self.week.__str__()]))

        page = bs(r.text, features='html.parser')

        # Find the team names
        names = page.findAll('span', {'class': 'first_name'})
        teams = {
            x.text: '/'.join(
                [url, 'schools', self.year.__str__(), self.week.__str__(), '-'.join(x.text.split()).lower()])
            for x in names}

        self.ballots['voters'] = {}

        for team in teams:
            r = super().scrape(teams[team])
            print("retrieved {}".format(team))

            # Find the ballot table
            rows = bs(r.text, features='html.parser').findAll('tr',
                                                              {'class': re.compile(r'ballot-ranking-row*')})

            # The structure of these data are to give us the team, then who voted for them. We'll work backwards.
            for row in rows:
                coach = row.contents[1].text.strip()
                coach_team = row.contents[3].text.strip()
                rank = int(row.contents[5].text.strip())
                if coach not in self.ballots['voters']:
                    self.ballots['voters'][coach] = {'team': coach_team, 'rankings': []}
                self.ballots['voters'][coach]['rankings'].append([team, rank])

        for v in self.ballots['voters']:
            l = ['' for x in range(0, 25)]
            for x in sorted(self.ballots['voters'][v]['rankings'], key=lambda x: x[1]):
                l[x[1] - 1] = x[0]
            self.ballots['voters'][v]['rankings'] = l

    def table_csv(self, file=None, transpose=False):
        if not file:
            if transpose:
                file = ' '.join([str(self.year), 'Week', str(self.week), 'Coaches Poll Transposed.csv'])
            else:
                file = ' '.join([str(self.year), 'Week', str(self.week), 'Coaches Poll.csv'])
        # super().table_csv(file=file, transpose=transpose)
        with open(file, 'w+', newline='') as outfile:
            csvwriter = csv.writer(outfile)
            if not transpose:
                csvwriter.writerow([''] + [x for x in self.ballots['voters']])
                csvwriter.writerow(
                    ['Rank'] + [self.ballots['voters'][x]['team'] for x in self.ballots['voters']])
                for i in range(0, 25):
                    row = [i + 1]
                    for voter in self.ballots['voters']:
                        row.append(self.ballots['voters'][voter]['rankings'][i])
                    csvwriter.writerow(row)
            else:
                csvwriter.writerow(['Voter', 'Team Coached'] + [x + 1 for x in range(0, 25)])
                for voter in self.ballots['voters']:
                    csvwriter.writerow(
                        [voter] + [self.ballots['voters'][voter]['team']] + self.ballots['voters'][voter]['rankings'])


foo = APPoll(year=2018)
foo.scrape()
foo.json_out()
foo.flat_csv()
foo.table_csv()
foo.table_csv(transpose=True)

foo = CoachesPoll(year=2018, week=1)
foo.scrape()
foo.json_out()
foo.flat_csv()
foo.table_csv()
foo.table_csv(transpose=True)
