import csv
import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup as bs


class Poll(object):

    def __init__(self, year=2018, week=1):
        self.ballots = {}
        self.date = None
        self.year = year
        if week in range(1, 16):
            self.week = week
        else:
            self.week = 1

    def flatten(self):
        out = []
        for v in self.ballots['voters']:
            i = 1
            for t in self.ballots['voters'][v]:
                out.append([self.date.strftime('%x'), v, i, t])
                i += 1
        return out

    def flat_csv(self, file=None):
        result = self.flatten()
        with open(file, 'w+', newline='') as outfile:
            csvwriter = csv.writer(outfile)
            for row in result:
                csvwriter.writerow(row)

    def json_out(self, file=None):
        with open(file, 'w+') as outfile:
            json.dump(self.ballots, outfile, indent=4, sort_keys=True)

    def scrape(self):
        pass

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

    def flat_csv(self, file=None):
        if not file:
            file = ' '.join(['Flat', str(self.year), 'Week', str(self.week), 'AP Poll.csv'])

        super().flat_csv(file)

    def json_out(self, file=None):
        if not file:
            file = ' '.join([str(self.year), 'Week', str(self.week), 'AP Poll.json'])

        super().json_out(file)

    def scrape(self):
        # the AP records all 2018 seasons as "2019"
        year = self.year
        if year == datetime.now().year:
            year += 1

        headers = {'User-Agent': 'Mozilla/5.0'}
        url = '/'.join(['https://collegefootball.ap.org/poll', str(year), str(self.week)])

        # request the page
        r = requests.get(url, headers=headers)
        if r.status_code == 404:
            r.raise_for_status()
        else:
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
                r = requests.get(voters[v], headers=headers)

                # Find the ballot table
                table = bs(r.text, features='html.parser').find('table')

                # get the rows
                rows = table.findAll('tr', {'class': re.compile('[0-9]*')})

                # Make a length 25 list
                self.ballots['voters'][v] = ['none' for x in range(0, 25)]

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


foo = APPoll(year=2018)
foo.scrape()
foo.json_out()
foo.flat_csv()
foo.table_csv()
foo.table_csv(transpose=True)
