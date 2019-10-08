#!/usr/bin/env python3
from copy import copy

class SimulatorM5PModel:

	def __init__(self, last_mcs, last_length, cur_mcs, statistics):
		self.max_length_th = dict()
		self.candidates = []

		self._last_mcs = last_mcs
		self._last_length = last_length
		self._cur_mcs = cur_mcs
		self._statistics = statistics

		self.success_tx_global_channel_utilization = statistics["success_tx_global_channel_utilization"]
		self.success_ratio_per = statistics["success_ratio_per"]

		self.previous_statistics = {}
		self.second_statistics = {}
		self.last_counter = 0
		self._black = {}

	@property
	def black(self):
		"""Get bl;ack."""

		return self._black

	@black.setter
	def black(self, black):
		"""Set the last_mcs."""

		self._black = black

		print("--- black ", black)

	@property
	def last_mcs(self):
		"""Get last_mcs."""

		return self._last_mcs

	@last_mcs.setter
	def last_mcs(self, last_mcs):
		"""Set the last_mcs."""

		self._last_mcs = last_mcs

		print("--- last_mcs ", last_mcs)

	@property
	def last_length(self):
		"""Get last_length."""

		return self._last_length

	@last_length.setter
	def last_length(self, last_length):
		"""Set the last_length."""

		self._last_length = last_length

		print("--- last_length ", last_length)

	@property
	def cur_mcs(self):
		"""Get cur_mcs."""

		return self._cur_mcs

	@cur_mcs.setter
	def cur_mcs(self, cur_mcs):
		"""Set the cur_mcs."""

		self._cur_mcs = cur_mcs

		print("--- cur_mcs ", cur_mcs)

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

		print("--- self.success_tx_global_channel_utilization ", self.success_tx_global_channel_utilization)
		print("--- self.success_ratio_per ", self.success_ratio_per)

	def estimate_optimal_length(self):

		self.candidates = []

		if self.cur_mcs == 0:
			self.candidates = [self.mcs0_550(), self.mcs0_1024(), self.mcs0_2048(), self.mcs0_3839()]
		elif self.cur_mcs == 1:
			self.candidates = [self.mcs1_550(), self.mcs1_1024(), self.mcs1_2048(), self.mcs1_3839()]
		elif self.cur_mcs == 2:
			self.candidates = [self.mcs2_550(), self.mcs2_1024(), self.mcs2_2048(), self.mcs2_3839()]
		elif self.cur_mcs == 3:
			self.candidates = [self.mcs3_550(), self.mcs3_1024(), self.mcs3_2048(), self.mcs3_3839()]
		elif self.cur_mcs == 4:
			self.candidates = [self.mcs4_550(), self.mcs4_1024(), self.mcs4_2048(), self.mcs4_3839()]
		elif self.cur_mcs == 5:
			self.candidates = [self.mcs5_550(), self.mcs5_1024(), self.mcs5_2048(), self.mcs5_3839()]
		elif self.cur_mcs == 6:
			self.candidates = [self.mcs6_550(), self.mcs6_1024(), self.mcs6_2048(), self.mcs6_3839()]
		elif self.cur_mcs == 7:
			self.candidates = [self.mcs7_550(), self.mcs7_1024(), self.mcs7_2048(), self.mcs7_3839()]

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
		# current one is less than 5%, then we do not increase overhead
		# by changing frame length
		# if self.last_mcs is not None:
		# 	if self.last_mcs == self.cur_mcs:
		# 		last_output = "mcs" + str(self.last_mcs) + "_" + str(self.last_length)
		# 		last_th_expected = eval('self.' + last_output + '()')

		# 		if ((self.max_length_th["expected_th"] - last_th_expected["expected_th"]) / last_th_expected["expected_th"]) < 0.05:
		# 			self.max_length_th["expected_th"] = last_th_expected
		# 			self.max_length_th["length"] = self.last_length

		# print(self.max_length_th)
		return self.max_length_th


	def mcs0_550(self):

		expected_th = 0.1065 * self.success_ratio_per 

		return {'length': 550, 'expected_th': expected_th}

	def mcs0_1024(self):

		expected_th = 0

		if self.success_ratio_per > 78.819:
			expected_th = 7.4693 * self.success_tx_global_channel_utilization \
						+ 0.11 * self.success_ratio_per \
						- 4.6582

		elif self.success_tx_global_channel_utilization > 0.614:
			expected_th = 0.5711 * self.success_tx_global_channel_utilization \
						+ 0.1122 * self.success_ratio_per \
						- 0.3711

		else:
			expected_th = 0.1065 * self.success_ratio_per 

		return {'length': 1024, 'expected_th': expected_th}

	def mcs0_2048(self):

		expected_th = 0

		if self.success_ratio_per > 91.498 and self.success_tx_global_channel_utilization > 0.672:
			expected_th = 0.8746 * self.success_tx_global_channel_utilization \
						+ 0.1072 * self.success_ratio_per \
						- 0.1556
		else:
			expected_th = 4.3735 * self.success_tx_global_channel_utilization \
						+ 0.1079 * self.success_ratio_per \
						- 2.8601

		return {'length': 2048, 'expected_th': expected_th}

	def mcs0_3839(self):

		expected_th = 0

		if self.success_ratio_per > 93.638 and self.success_tx_global_channel_utilization <= 0.795 and self.success_tx_global_channel_utilization > 0.698:
			expected_th = 0.841 * self.success_tx_global_channel_utilization \
						+ 0.0979 * self.success_ratio_per \
						+ 0.7236

		elif self.success_ratio_per <= 96.612:
			expected_th = 3.6633 * self.success_tx_global_channel_utilization \
						+ 0.1024 * self.success_ratio_per \
						- 1.9955

		else:
			expected_th = -0.1888 * self.success_tx_global_channel_utilization \
						+ 0.1118 * self.success_ratio_per \
						+ 0.1685

		return {'length': 3839, 'expected_th': expected_th}

	def mcs1_550(self):

		expected_th = 0.2044 * self.success_ratio_per

		return {'length': 550, 'expected_th': expected_th}

	def mcs1_1024(self):

		expected_th = 0

		if self.success_ratio_per > 79.686:
			expected_th = 16.7195 * self.success_tx_global_channel_utilization \
						+ 0.2136 * self.success_ratio_per \
						- 9.7194

		else:
			expected_th = 0.2143 * self.success_ratio_per \
						- 0.0133

		return {'length': 1024, 'expected_th': expected_th}

	def mcs1_2048(self):

		expected_th = 0

		if self.success_ratio_per > 90.82 and self.success_tx_global_channel_utilization > 0.673:
			expected_th = 0.88 * self.success_tx_global_channel_utilization \
						+ 0.225 * self.success_ratio_per \
						- 1.7453

		elif self.success_ratio_per > 85.741 and self.success_ratio_per <= 97.17:
			expected_th = 10.8694 * self.success_tx_global_channel_utilization \
						+ 0.207 * self.success_ratio_per \
						- 6.7998

		elif self.success_ratio_per <= 90.46:
			expected_th = 4.8577 * self.success_tx_global_channel_utilization \
						+ 0.2104 * self.success_ratio_per \
						- 3.2008

		else:
			expected_th = 0.2044 * self.success_ratio_per \
						+ 0.0009

		return {'length': 2048, 'expected_th': expected_th}

	def mcs1_3839(self):

		expected_th = 0

		if self.success_ratio_per > 97.881 and self.success_tx_global_channel_utilization <= 0.798 and self.success_tx_global_channel_utilization > 0.776:
			expected_th = 1.6119 * self.success_tx_global_channel_utilization \
						+ 0.01 * self.success_ratio_per \
						+ 18.8831

		elif self.success_ratio_per <= 97.785:
			expected_th = 9.7826 * self.success_tx_global_channel_utilization \
						+ 0.207 * self.success_ratio_per \
						- 6.5827

		elif self.success_tx_global_channel_utilization <= 0.785 and self.success_tx_global_channel_utilization > 0.752:
			expected_th = 1.3728 * self.success_tx_global_channel_utilization \
						+ 0.1229 * self.success_ratio_per \
						+ 7.7557
			
		elif self.success_tx_global_channel_utilization > 0.771:
			expected_th = 0.0483 * self.success_ratio_per \
						+ 16.5091

		elif self.success_tx_global_channel_utilization > 0.693:
			expected_th = 2.9636 * self.success_tx_global_channel_utilization \
						+ 0.2102 * self.success_ratio_per \
						- 1.7841

		else:
			expected_th = 20.0043

		return {'length': 3839, 'expected_th': expected_th}

	def mcs2_550(self):

		expected_th = 0.2935 * self.success_ratio_per 

		return {'length': 550, 'expected_th': expected_th}

	def mcs2_1024(self):

		expected_th = 0

		if self.success_ratio_per > 59.744:
			expected_th = 26.3252 * self.success_tx_global_channel_utilization \
						+ 0.3032 * self.success_ratio_per \
						- 13.5384

		else:
			expected_th = 0.8266 * self.success_tx_global_channel_utilization \
						+ 0.3062 * self.success_ratio_per \
						- 0.4331

		return {'length': 1024, 'expected_th': expected_th}

	def mcs2_2048(self):

		expected_th = 0

		if self.success_ratio_per > 92.165 and self.success_tx_global_channel_utilization > 0.59 and self.success_ratio_per <= 97.568:
			expected_th = 1.0879 * self.success_tx_global_channel_utilization \
						+ 0.2707 * self.success_ratio_per \
						+ 2.9104

		elif self.success_ratio_per > 86.382 and self.success_tx_global_channel_utilization > 0.606:
			expected_th = 3.2049 * self.success_tx_global_channel_utilization \
						+ 0.0235 * self.success_ratio_per \
						+ 25.7931
		else:
			expected_th = 7.462 * self.success_tx_global_channel_utilization \
						+ 0.2943 * self.success_ratio_per \
						- 4.2939

		return {'length': 2048, 'expected_th': expected_th}

	def mcs2_3839(self):

		expected_th = 0

		if self.success_ratio_per <= 98.78 and self.success_tx_global_channel_utilization > 0.677:
			expected_th = 10.8869 * self.success_tx_global_channel_utilization \
						+ 0.2995 * self.success_ratio_per \
						- 7.1359
		else:
			expected_th = 12.6973 * self.success_tx_global_channel_utilization \
						+ 0.2929 * self.success_ratio_per \
						- 8.0281

		return {'length': 3839, 'expected_th': expected_th}

	def mcs3_550(self):

		expected_th = 0.3805 * self.success_ratio_per 

		return {'length': 550, 'expected_th': expected_th}

	def mcs3_1024(self):

		expected_th = 0

		if self.success_ratio_per > 53.832:
			expected_th = 0.3923 * self.success_ratio_per \
						- 0.7937

		else:
			expected_th = -0.011 * self.success_tx_global_channel_utilization \
						+ 0.3879 * self.success_ratio_per \
						- 0.0008

		return {'length': 1024, 'expected_th': expected_th}

	def mcs3_2048(self):

		expected_th = 0.3861 * self.success_ratio_per \
					+ 0.0068

		return {'length': 2048, 'expected_th': expected_th}

	def mcs3_3839(self):

		expected_th = 0

		if self.success_ratio_per > 98.993:
			expected_th = 0.0497 * self.success_ratio_per \
						+ 33.6317

		elif self.success_ratio_per <= 81.211:
			expected_th = 0.3888 * self.success_ratio_per \
						- 0.0021

		else:
			expected_th = 0.3339 * self.success_ratio_per \
						+ 4.6991

		return {'length': 3839, 'expected_th': expected_th}


	def mcs4_550(self):

		expected_th = 0.5327 * self.success_ratio_per

		return {'length': 550, 'expected_th': expected_th}

	def mcs4_1024(self):

		expected_th = 0.5375 * self.success_ratio_per \
					- 0.0447

		return {'length': 1024, 'expected_th': expected_th}

	def mcs4_2048(self):

		expected_th = 2.1708 * self.success_tx_global_channel_utilization \
					+ 0.5375 * self.success_ratio_per \
					- 1.0886

		return {'length': 2048, 'expected_th': expected_th}

	def mcs4_3839(self):

		expected_th = 0

		if self.success_ratio_per <= 99.552:
			expected_th = 20.7865 * self.success_tx_global_channel_utilization \
						+ 0.504 * self.success_ratio_per \
						- 9.3981

		elif self.success_tx_global_channel_utilization > 0.654:
			expected_th = 1.0183 * self.success_tx_global_channel_utilization \
						+ 0.4926 * self.success_ratio_per \
						+ 3.9707

		else:
			expected_th = 0.5409 * self.success_ratio_per \
						- 0.012

		return {'length': 3839, 'expected_th': expected_th}

	def mcs5_550(self):

		expected_th = 0.6632 * self.success_ratio_per 

		return {'length': 550, 'expected_th': expected_th}

	def mcs5_1024(self):

		expected_th = 44.6962 * self.success_tx_global_channel_utilization \
					+ 0.6693 * self.success_ratio_per \
					- 15.0703

		return {'length': 1024, 'expected_th': expected_th}

	def mcs5_2048(self):

		expected_th = 0

		if self.success_ratio_per > 96.875 and self.success_tx_global_channel_utilization <= 0.499:
			expected_th = 2.5334 * self.success_tx_global_channel_utilization \
						+ 0.0791 * self.success_ratio_per \
						+ 57.4858

		elif self.success_ratio_per > 51.569 and self.success_ratio_per <= 97.661 and self.success_tx_global_channel_utilization <= 0.499:
			expected_th = -10.7856 * self.success_tx_global_channel_utilization \
						+ 0.1185 * self.success_ratio_per \
						+ 56.4639

		elif self.success_ratio_per <= 51.569:
			expected_th = 0.6831 * self.success_ratio_per \
						- 0.0727

		else:
			expected_th = 0.6947 * self.success_ratio_per \

		return {'length': 2048, 'expected_th': expected_th}

	def mcs5_3839(self):

		expected_th = 0

		if self.success_tx_global_channel_utilization <= 0.626 and self.success_ratio_per > 99.708:
			expected_th = 6.9998 * self.success_tx_global_channel_utilization \
						+ 0.0932 * self.success_ratio_per \
						+ 53.8532

		elif self.success_tx_global_channel_utilization > 0.626 and self.success_tx_global_channel_utilization <= 0.635:
			expected_th = -10.4231 * self.success_tx_global_channel_utilization \
						+ 0.0416 * self.success_ratio_per \
						+ 70.2946

		elif self.success_tx_global_channel_utilization > 0.628:
			expected_th = 4.761 * self.success_tx_global_channel_utilization \
						+ 0.0808 * self.success_ratio_per \
						+ 56.6005

		elif self.success_ratio_per <= 98.705 and self.success_tx_global_channel_utilization <= 0.585:
			expected_th = 7.4106 * self.success_tx_global_channel_utilization \
						+ 0.4835 * self.success_ratio_per \
						+ 13.544

		elif self.success_ratio_per <= 96.831:
			expected_th = 12.9709 * self.success_tx_global_channel_utilization \
						+ 0.1891 * self.success_ratio_per \
						+ 39.7829

		elif self.success_tx_global_channel_utilization <= 0.585:
			expected_th = 12.0964 * self.success_tx_global_channel_utilization \
						+ 59.2605

		else:
			expected_th = 0.6949 * self.success_ratio_per \
						- 0.0143

		return {'length': 3839, 'expected_th': expected_th}

	def mcs6_550(self):

		expected_th = 0.7262 * self.success_ratio_per 

		return {'length': 550, 'expected_th': expected_th}

	def mcs6_1024(self):

		expected_th = -53.9376 * self.success_tx_global_channel_utilization \
					+ 0.7194 * self.success_ratio_per \
					+ 16.9493

		return {'length': 1024, 'expected_th': expected_th}

	def mcs6_2048(self):

		expected_th = 0

		if self.success_ratio_per > 51.788 and self.success_ratio_per <= 96.657:
			expected_th = -0.2507 * self.success_tx_global_channel_utilization \
						+ 0.6994 * self.success_ratio_per \
						+ 2.3779

		elif self.success_ratio_per > 61.563:
			expected_th = -0.5177 * self.success_tx_global_channel_utilization \
						+ 0.0663 * self.success_ratio_per \
						+ 65.3986

		else:
			expected_th = -1.6826 * self.success_tx_global_channel_utilization \
						+ 0.7299 * self.success_ratio_per \
						+ 0.662

		return {'length': 2048, 'expected_th': expected_th}

	def mcs6_3839(self):

		expected_th = 0

		if self.success_tx_global_channel_utilization <= 0.583:
			expected_th = -24.731 * self.success_tx_global_channel_utilization \
						+ 0.6963 * self.success_ratio_per \
						+ 15.9811

		elif self.success_tx_global_channel_utilization <= 0.603:
			expected_th = 6.418 * self.success_tx_global_channel_utilization \
						+ 0.6908 * self.success_ratio_per \
						- 0.0373

		elif self.success_tx_global_channel_utilization <= 0.612:
			expected_th = 10.2135 * self.success_tx_global_channel_utilization \
						+ 0.7072 * self.success_ratio_per \
						- 3.4352

		else:
			expected_th = -0.0961 * self.success_tx_global_channel_utilization \
						+ 0.7391 * self.success_ratio_per \
						+ 0.0014

		return {'length': 3839, 'expected_th': expected_th}

	def mcs7_550(self):

		expected_th = 0.7719 * self.success_ratio_per

		return {'length': 550, 'expected_th': expected_th}

	def mcs7_1024(self):

		expected_th = 98.8624 * self.success_tx_global_channel_utilization \
					+ 0.7832 * self.success_ratio_per \
					- 29.3012

		return {'length': 1024, 'expected_th': expected_th}

	def mcs7_2048(self):

		expected_th = 0

		if self.success_ratio_per > 49.435:
			expected_th = 10.1735 * self.success_tx_global_channel_utilization \
						+ 0.7847 * self.success_ratio_per \
						- 4.7744

		else:
			expected_th = 0.7122 * self.success_tx_global_channel_utilization \
						+ 0.7716 * self.success_ratio_per \
						- 0.2459

		return {'length': 2048, 'expected_th': expected_th}

	def mcs7_3839(self):

		expected_th = 0

		if self.success_ratio_per > 99.883 and self.success_tx_global_channel_utilization > 0.576:
			expected_th = 40.1983 * self.success_tx_global_channel_utilization \
						+ 0.344 * self.success_ratio_per \
						+ 19.7195

		elif self.success_tx_global_channel_utilization <= 0.544:
			expected_th = 2.2553 * self.success_tx_global_channel_utilization \
						+ 1.1655 * self.success_ratio_per \
						- 40.4109

		elif self.success_tx_global_channel_utilization <= 0.571:
			expected_th = -40.6888 * self.success_tx_global_channel_utilization \
						+ 102.3039

		else:
			expected_th = 0.7803 * self.success_ratio_per \
						+ 0.0278

		return {'length': 3839, 'expected_th': expected_th}