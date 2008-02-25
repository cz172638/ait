#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

import ethtool, schedutils, sys, time, procfs

def softirq_info(rxtx):
	print "\nSoft IRQ net %s info" % rxtx
	pids = ps.find_by_name("softirq-net-%s/" % rxtx)
	print "%5s %5s %7s" % ("pid", "rtpri", "affinity")
	for pid in pids:
		affinity = ",".join("%s" % a for a in schedutils.get_affinity(pid))
		rtprio = int(ps[pid]["stat"]["rt_priority"])
		print "%5d %5d %8s" % (pid, rtprio, affinity)

def show_header():
	print "Hard IRQ info"
	print "%5s  %5s %5s %11s %7s    %s" % (" ", " ", " ", " ", "thread", "IRQ")
	print "%5s: %5s %5s %11s %7s %7s %s" % ("irq", "pid", "rtpri", "events", "affinity", "affinity", "users")

def show(irqs, ps):
	irq_list = []
	for sirq in irqs.keys():
		try:
			irq_list.append(int(sirq))
		except:
			continue

	irq_list.sort()

	nics = ethtool.get_active_devices()

	for irq in irq_list:
		info = irqs[irq]
		pids = ps.find_by_name("IRQ-%d" % irq)
		if pids:
			pid = pids[0]
			thread_affinity_list = schedutils.get_affinity(pid)
			if len(thread_affinity_list) <= 4:
				thread_affinity = ",".join("%s" % a for a in thread_affinity_list)
			else:
				thread_affinity = ",".join("0x%x" % a for a in procfs.hexbitmask(schedutils.get_affinity(pid), irqs.nr_cpus))
			rtprio = int(ps[pid]["stat"]["rt_priority"])
		else:
			pid = -1
			rtprio = -1
			thread_affinity = ""

		try:
			irq_affinity_list = info["affinity"]
			if len(irq_affinity_list) <= 4:
				irq_affinity = ",".join("%s" % a for a in irq_affinity_list)
			else:
				irq_affinity = ",".join("0x%x" % a for a in procfs.hexbitmask(irq_affinity_list, irqs.nr_cpus))
		except:
			irq_affinity = ""
		events = reduce(lambda a, b: a + b, info["cpu"])
		users = info["users"]
		for u in users:
			if u in nics:
				users[users.index(u)] = "%s(%s)" % (u, ethtool.get_module(u))
		print "%5d: %5d %5d %11d %8s %8s %s" % (irq, pid, rtprio,
							events, thread_affinity,
						        irq_affinity,
						        ",".join(users))

if __name__ == '__main__':

	irqs = procfs.interrupts()
	ps = procfs.pidstats()

	show_header()
	show(irqs, ps)

	try:
		interval = int(sys.argv[1])
		while True:
			time.sleep(interval)
			irqs.reload()
			ps.reload()

			show_header()
			show(irqs, ps)
	except:
		for direction in [ "rx", "tx" ]:
			softirq_info(direction)
