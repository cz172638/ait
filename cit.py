#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

from dbstats import dbstats

class rates_report:
	def __init__(self, filename):
		self.rates = {}
		self._load_latencies_report(filename)

	def _load_latencies_report(self, filename):
		try:
			f = file(filename)
		except:
			return
		for line in f.readlines():
			fields = line.strip().split(',')
			rate = int(fields[0])

			self.rates[rate] = tuple([float(i) for i in fields[1:-1]]) + (int(fields[-1]),)
		f.close()

if __name__ == '__main__':
	import sys

	appname = sys.argv[1]
	server_process_name = sys.argv[2]
	client_machine = sys.argv[3]
	report = sys.argv[4]

	db = dbstats(appname)

	if not db.setreport(report, server_process_name, client_machine):
		print "report %s already in database" % report
		sys.exit(1)

	r = rates_report("%s.cit" % report)
	db.insert_table(r.rates)
