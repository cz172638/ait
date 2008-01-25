#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

import ethtool, procfs, schedutils, sys, time, utilist

def show_header():
	print "RT threads"
	print "%5s %6s %5s %7s       %s" % (" ", " ", " ", "thread", "ctxt_switches")
	print "%5s %6s %5s %7s %9s %12s %15s %s" % ("pid", "SCHED_", "rtpri", "affinity", "voluntary", "nonvoluntary", "cmd", "IRQ users")

def show(ps, cpuinfo, irqs):
	ps_list = []
	for pid in ps.keys():
		if schedutils.get_scheduler(pid) == 0:
			continue
		ps_list.append(pid)

	ps_list.sort()

	nics = ethtool.get_active_devices()

	for pid in ps_list:
		thread_affinity_list = schedutils.get_affinity(pid)
		if len(thread_affinity_list) <= 4:
			thread_affinity = ("%s" % thread_affinity_list)[1:-1].replace(" ", "")
		else:
			thread_affinity = utilist.csv(utilist.hexbitmask(schedutils.get_affinity(pid), cpuinfo.nr_cpus), '0x%x')
		sched = schedutils.schedstr(schedutils.get_scheduler(pid))[6:]
		rtprio = int(ps[pid]["stat"]["rt_priority"])
		cmd = ps[pid]["stat"]["comm"]
		users = ""
		if cmd[:4] == "IRQ-":
			try:
				users = irqs[cmd[4:]]["users"]
				for u in users:
					if u in nics:
						users[users.index(u)] = "%s(%s)" % (u, ethtool.get_module(u))
				users = utilist.csv(users, "%s")
			except:
				users = "Not found in /proc/interrupts!"
		try:
			voluntary_ctxt_switches = int(ps[pid]["status"]["voluntary_ctxt_switches"])
			nonvoluntary_ctxt_switches = int(ps[pid]["status"]["nonvoluntary_ctxt_switches"])
		except:
			voluntary_ctxt_switches = -1
			nonvoluntary_ctxt_switches = -1
		print "%5d %6s %5d %8s %9d %12s %15s %s" % (pid, sched, rtprio,
							    thread_affinity,
							    voluntary_ctxt_switches,
							    nonvoluntary_ctxt_switches,
							    cmd, users)

if __name__ == '__main__':

	ps = procfs.stats()
	cpuinfo = procfs.cpuinfo()
	irqs = procfs.interrupts()

	show_header()
	show(ps, cpuinfo, irqs)

	try:
		interval = int(sys.argv[1])
		while True:
			time.sleep(interval)
			ps.reload()

			show_header()
			show(ps, cpuinfo, irqs)
	except:
		pass
