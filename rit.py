#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

try:
	from sqlite3 import connect as sqlite3_connect
except:
	from sqlite import connect as sqlite3_connect

from dbstats import dbstats

def get_rates(db, server, client):
	db.cursor.execute('''
				select distinct res.rate
				  from results res,
				       report rep,
				       environment e,
				       machine m,
				       client_machine client
				  where res.report = rep.rowid and
				  	rep.env = e.rowid and
				  	rep.client_env = client.rowid and
					e.machine = m.rowid and
					m.nodename = "%s" and
					client.nodename = "%s"
				  order by res.rate
			  ''' % (server, client))
	results = db.cursor.fetchall()
	if results:
		return [r[0] for r in results]
	return None

def get_kernel_releases(db, server, client):
	db.cursor.execute('''
				select distinct s.kernel_release
				  from results res,
				       report rep,
				       environment e,
				       client_machine client,
				       machine m,
				       software_versions s
				  where res.report = rep.rowid and
				  	rep.env = e.rowid and
				  	rep.client_env = client.rowid and
					e.machine = m.rowid and
					e.software_versions = s.rowid and
					m.nodename = "%s" and
					client.nodename = "%s"
				  order by res.rate
			  ''' % (server, client))
	results = db.cursor.fetchall()
	if results:
		return [k[0] for k in results]
	return None

def get_kernel_max_rate(db, kernel, server, client):
	db.cursor.execute('''
				select max(res.rate)
				  from results res,
				       report rep,
				       environment e,
				       client_machine client,
				       machine m,
				       software_versions s
				  where res.report = rep.rowid and
				  	rep.env = e.rowid and
				  	rep.client_env = client.rowid and
					e.machine = m.rowid and
					e.software_versions = s.rowid and
					m.nodename = "%s" and
					client.nodename = "%s" and
					s.kernel_release = "%s"
			  ''' % (server, client, kernel))
	result = db.cursor.fetchone()
	if result:
		return int(result[0])
	return None

def get_latest_report_id(db):
	db.cursor.execute('select max(rowid) from report')
	result = db.cursor.fetchone()
	if result:
		return int(result[0])
	return None

def get_results(db, rate, result_field, server, client):
	db.cursor.execute('''
				select distinct res.report,
				       rep.env,
				       e.tunings,
				       s.kernel_release,
				       res.%s,
				       t.*,
				       client.nodename
				  from results res,
				       report rep,
				       environment e,
				       machine m,
				       client_machine client,
				       tunings t,
				       software_versions s
				  where res.report = rep.rowid and
				  	rep.env = e.rowid and
					rep.client_env = client.rowid and
					e.machine = m.rowid and
					e.software_versions = s.rowid and
					e.tunings = t.rowid and
					res.rate = %d and
					m.nodename = "%s" and
					client.nodename = "%s"
				  order by res.%s
				  limit 10
			  ''' % (result_field, rate, server, client, result_field))
	return db.cursor.fetchall()

def get_common_columns(results, columns):
	common_columns = []
	for column_index in range(len(columns)):
		if len(list(set([result[column_index] for result in results]))) == 1:
			common_columns.append(column_index)

	return common_columns

def remove_common_columns(columns, common_columns):
	result = []
	for i in range(len(columns)):
		if i not in common_columns:
			result.append(columns[i])

	return result

def print_rate(db, rate, server, client):
	print "rate: %d" % rate
	print "-" * 78
	for result_field in ("avg", "min", "max", "dev"):
		results = get_results(db, rate, result_field, server, client)

		columns = [column[0] for column in db.cursor.description]
		common_columns = get_common_columns(results, columns)
		print "Shared tunings:"
		for column_index in common_columns:
			value = results[0][column_index]
			if value:
				print "%s: %s" % (columns[column_index], value)

		if len(columns) == len(common_columns):
			continue

		columns = remove_common_columns(columns, common_columns)
		for i in range(len(results)):
			results[i] = remove_common_columns(results[i], common_columns)

		max_mask_lens = [len(column) for column in columns]
		for result in results:
			mask_lens = [len(str(column)) for column in result]
			for i in range(len(mask_lens)):
				if mask_lens[i] > max_mask_lens[i]:
					max_mask_lens[i] = mask_lens[i]
			
		mask_lens = ["%%%ds | " % l for l in max_mask_lens]
		mask = reduce(lambda a, b: a + b, mask_lens)
		print mask % tuple(columns)

		for result in results:
			print mask % tuple([str(i) for i in result])
		print

if __name__ == '__main__':
	import sys

	appname = sys.argv[1]
	server = sys.argv[2]
	client = sys.argv[3]

	db = dbstats(appname)
	rates = get_rates(db, server, client)
	print "server: %s\n" % server
	print "client: %s\n" % client

	latest_report = get_latest_report_id(db)
	if not latest_report:
		print "No reports found!"
		sys.exit(1)

	print "latest report info:"
	print "  report id: %d" % latest_report
	print "  kernel: %s" % db.get_kernel_release_for_report(latest_report)
	print "  max rate: " + str(db.get_max_rate_for_report(latest_report)) + "\n"

	kernels = get_kernel_releases(db, server, client)
	kernels.sort()
	width = max([len(i) for i in kernels])
	mask = "%%-%ds: %%d" % width
	print "max rates per kernel release:\n"
	for k in kernels:
		print mask % (k, get_kernel_max_rate(db, k, server, client))

	print
	for rate in rates:
		try:
			print_rate(db, rate, server, client)
		except IOError:
			break
