#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

from dbstats import dbstats

class latencies_per_rate_report:
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

			self.rates[rate] = tuple([float(i) for i in fields[1:]])
		f.close()

if __name__ == '__main__':
	import sys, os

	appname = sys.argv[1]
	server_process_name = sys.argv[2]
	client_machine = sys.argv[3]
	server_machine = sys.argv[4]
	report = sys.argv[5]

	db = dbstats(appname)

	if not db.setreport(report, server_process_name,
			    client_machine, server_machine):
		print "report %s already in database" % report
		sys.exit(1)

	r = latencies_per_rate_report("%s.cit" % report)
	metrics = [ "min", "avg", "max", "dev" ]
	for metric in range(len(metrics)):
		metric_rates = {}
		for rate in r.rates.keys():
			metric_rates[rate] = r.rates[rate][metric]
		db.insert_latency_per_rate(metrics[metric], metric_rates)

	if os.access("/proc/lock_stat", os.F_OK) and \
	   os.access("lock_stat/last", os.F_OK):
	   	os.rename("lock_stat/last", "lock_stat/%d.txt" % db.report)
