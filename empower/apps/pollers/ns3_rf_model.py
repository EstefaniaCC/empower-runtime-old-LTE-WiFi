#!/usr/bin/env python

from sklearn.externals import joblib
import pandas as pd
import os
from copy import copy

class SimulatorRFModel:

	def __init__(self, last_mcs, last_length, cur_mcs, statistics):
		self.max_length_th = dict()
		self.candidates = []

		self._last_mcs = last_mcs
		self._last_length = last_length
		self._cur_mcs = cur_mcs
		self._statistics = statistics
		self._black = {}

		self.success_tx_global_channel_utilization = statistics["success_tx_global_channel_utilization"]
		self.success_ratio_per = statistics["success_ratio_per"]

		self.features = ["success_tx_global_channel_utilization", "success_ratio_per"]

		self.previous_statistics = {}
		self.second_statistics = {}
		self.last_counter = 0

	@property
	def black(self):
		"""Get bl;ack."""

		return self._black

	@black.setter
	def black(self, black):
		"""Set the last_mcs."""

		self._black = black

	@property
	def last_mcs(self):
		"""Get last_mcs."""

		return self._last_mcs

	@last_mcs.setter
	def last_mcs(self, last_mcs):
		"""Set the last_mcs."""

		self._last_mcs = last_mcs

	@property
	def last_length(self):
		"""Get last_length."""

		return self._last_length

	@last_length.setter
	def last_length(self, last_length):
		"""Set the last_length."""

		self._last_length = last_length

	@property
	def cur_mcs(self):
		"""Get cur_mcs."""

		return self._cur_mcs

	@cur_mcs.setter
	def cur_mcs(self, cur_mcs):
		"""Set the cur_mcs."""

		self._cur_mcs = cur_mcs

	@property
	def statistics(self):
		"""Get statistics."""

		return self._statistics

	@statistics.setter
	def statistics(self, statistics):
		"""Set the statistics."""

		self._statistics = statistics

		self.success_tx_global_channel_utilization = statistics["success_tx_global_channel_utilization"]
		self.success_ratio_per = statistics["success_ratio_per"]

	def estimate_optimal_length(self):

		self.candidates = []
		len_1 = None
		len_2 = None
		len_3 = None
		len_4 = None

		X_data = [self.success_tx_global_channel_utilization,self.success_ratio_per]
		X_test = pd.DataFrame([X_data], columns=self.features)

		if self.cur_mcs == 0:
			len_1 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs0_550.pkl')
			len_2 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs0_1024.pkl')
			len_3 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs0_2048.pkl')
			len_4 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs0_3839.pkl')

		elif self.cur_mcs == 1:
			len_1 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs1_550.pkl')
			len_2 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs1_1024.pkl')
			len_3 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs1_2048.pkl')
			len_4 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs1_3839.pkl')

		elif self.cur_mcs == 2:
			len_1 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs2_550.pkl')
			len_2 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs2_1024.pkl')
			len_3 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs2_2048.pkl')
			len_4 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs2_3839.pkl')

		elif self.cur_mcs == 3:
			len_1 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs3_550.pkl')
			len_2 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs3_1024.pkl')
			len_3 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs3_2048.pkl')
			len_4 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs3_3839.pkl')

		elif self.cur_mcs == 4:
			len_1 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs4_550.pkl')
			len_2 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs4_1024.pkl')
			len_3 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs4_2048.pkl')
			len_4 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs4_3839.pkl')

		elif self.cur_mcs == 5:
			len_1 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs5_550.pkl')
			len_2 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs5_1024.pkl')
			len_3 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs5_2048.pkl')
			len_4 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs5_3839.pkl')

		elif self.cur_mcs == 6:
			len_1 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs6_550.pkl')
			len_2 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs6_1024.pkl')
			len_3 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs6_2048.pkl')
			len_4 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs6_3839.pkl')

		elif self.cur_mcs == 7:
			len_1 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs7_550.pkl')
			len_2 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs7_1024.pkl')
			len_3 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs7_2048.pkl')
			len_4 = joblib.load('/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs7_3839.pkl')

		self.candidates.append(len_1.predict(X_test).tolist()[0])
		self.candidates.append(len_2.predict(X_test).tolist()[0])
		self.candidates.append(len_3.predict(X_test).tolist()[0])
		self.candidates.append(len_4.predict(X_test).tolist()[0])

		if self.last_length:
			if not self.previous_statistics:
				self.previous_statistics = \
					{"length": self.last_length,
					"th": ((self.statistics["hist_success_bytes"] - self.statistics["previous_hist_success_bytes"]) / 1000000)}
			else:
				self.second_statistics = copy (self.previous_statistics)
				self.previous_statistics = \
					{"length": self.last_length,
					"th": ((self.statistics["hist_success_bytes"] - self.statistics["previous_hist_success_bytes"]) / 1000000)}

				if self.second_statistics["length"] != self.previous_statistics["length"]:
					self.last_counter = 0
				else:
					self.last_counter += 1

				if ((self.second_statistics["th"] - self.previous_statistics["th"]) / self.second_statistics["th"]) < -0.15 and \
					self.second_statistics["length"] != self.previous_statistics["length"]:

					if self.second_statistics["length"] not in self.black:
						self.black[self.second_statistics["length"]] = 10
						print("Putting %d in black list. Times %d" %(self.second_statistics["length"], self.black[self.second_statistics["length"]] ))
						print("Black list", self.black)
					else:
						self.black[self.second_statistics["length"]] += 10

				if ((self.previous_statistics["th"] - self.second_statistics["th"]) / self.previous_statistics["th"]) < -0.15 and \
					self.previous_statistics["length"] != self.second_statistics["length"]:

					if self.previous_statistics["length"] not in self.black:
						self.black[self.previous_statistics["length"]] = 10
						print("Putting %d in black list. Times %d" %(self.previous_statistics["length"], self.black[self.previous_statistics["length"]] ))
						print("Black list", self.black)
					else:
						self.black[self.previous_statistics["length"]] += 10

		if self.candidates:
			backup_candidates = copy(self.candidates)
			self.candidates = []
			for index, value in enumerate(backup_candidates):
				if (index == 0):
					self.candidates.append({'length': 550, 'expected_th': value})
				elif (index == 1):
					self.candidates.append({'length': 1024, 'expected_th': value})
				elif (index == 2):
					self.candidates.append({'length': 2048, 'expected_th': value})
				elif (index == 3):
					self.candidates.append({'length': 3839, 'expected_th': value})

		max_index = 0
		if self.candidates:
			print("*** Candidates ***")
			print(self.candidates)
			print("### Black list ###", self.black)
			for item in self.candidates:
				if item["length"] in self.black:
					item["expected_th"] *= (1-(self.black[item["length"]]/100))
			print("Candidates after adjustment", self.candidates)

			max_index = -1
			candidates_backup = copy(self.candidates)
			while max_index == -1 and len(self.candidates) > 0:
				max_index = max(range(len(self.candidates)), key=lambda index: self.candidates[index]['expected_th'])
				if self.black and self.candidates[max_index]["length"] in self.black:
					self.black[self.candidates[max_index]["length"]] -= 1
					if self.black[self.candidates[max_index]["length"]] == 0:
						del self.black[self.candidates[max_index]["length"]]
					del self.candidates[max_index]
					max_index = -1

			if max_index != -1:
				self.max_length_th = self.candidates[max_index]
				if "length" in self.previous_statistics:
					if self.candidates[max_index]["length"] != self.previous_statistics["length"]:
						self.last_counter = 0
			else:
				print("Index is -1")
				best_length = min(self.black, key=self.black.get)
				for i in candidates_backup:
					if i["length"] == best_length:
						self.max_length_th = i
						self.black[i["length"]] -= 1
						if self.black[i["length"]] == 0:
							del self.black[i["length"]]

			## If the same has been selected for a lot of times, we may try others slightly worse:
			if self.last_counter >= 5:
				self.last_counter = 0
				del self.candidates[max_index]
				second_max_index = -1

				while second_max_index == -1 and len(self.candidates) > 0:
					second_max_index = max(range(len(self.candidates)), key=lambda index: self.candidates[index]['expected_th'])
					if self.candidates[second_max_index]["length"] in self.black:

						self.black[self.candidates[second_max_index]["length"]] -= 1
						if self.black[self.candidates[second_max_index]["length"]] == 0:
							del self.black[self.candidates[second_max_index]["length"]]
						if len(self.candidates) == len(self.black):
							break
						del self.candidates[second_max_index]
						second_max_index = -1

				if second_max_index != -1:
					if ((self.max_length_th["expected_th"] - self.candidates[second_max_index]["expected_th"]) / self.candidates[second_max_index]["expected_th"]) < 0.05:
						self.max_length_th = self.candidates[second_max_index]
		else:
			self.max_length_th = {'length': self.last_length, 'expected_th': 0}
		

		# If the difference in the expected self.last_attempts_bytes with respect to the 
		# current len_1 is less than 5%, then we do not increase overhead
		# by changing frame length
		# if self.last_mcs is not None:
		# 	if self.last_mcs == self.cur_mcs:
		# 		last_output = "/home/estefania/5G-EmPOWER/empower-runtime/empower/apps/pollers/simulatorrf/mcs" + str(self.last_mcs) + "_" + str(self.last_length) + ".pkl"
		# 		last_model = joblib.load(last_output)
		# 		last_th_expected = {'length': self.last_length, 'expected_th': last_model.predict(X_test).tolist()[0]}

		# 		if ((self.max_length_th["expected_th"] - last_th_expected["expected_th"]) / last_th_expected["expected_th"]) < 0.05:
		# 			self.max_length_th["expected_th"] = last_th_expected
		# 			self.max_length_th["length"] = self.last_length

		return self.max_length_th