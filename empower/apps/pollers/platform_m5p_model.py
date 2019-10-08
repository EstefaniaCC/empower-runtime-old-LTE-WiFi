#!/usr/bin/env python3

from copy import copy

class PlatformM5PModel:

	def __init__(self, last_mcs, last_length, cur_mcs, statistics):
		self.max_length_th = dict()
		self.candidates = []

		self._last_mcs = last_mcs
		self._last_length = last_length
		self._cur_mcs = cur_mcs
		self._statistics = statistics
		self._black = {}

		self.minstrel_throughput = statistics["minstrel_throughput"]
		self.success_ratio = statistics["success_ratio"]
		self.last_attempts_bytes = statistics["last_attempts_bytes"]
		self.global_channel_utilization = statistics["global_channel_utilization"]

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

		print("--- cur_mcs ", cur_mcs)

	@property
	def statistics(self):
		"""Get statistics."""

		return self._statistics

	@statistics.setter
	def statistics(self, statistics):
		"""Set the statistics."""

		self._statistics = statistics

		self.minstrel_throughput = statistics["minstrel_throughput"]
		self.success_ratio = statistics["success_ratio"]
		self.last_attempts_bytes = statistics["last_attempts_bytes"]
		self.global_channel_utilization = statistics["global_channel_utilization"]

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

		return self.max_length_th

	def mcs0_550(self):

		expected_th = 0

		if self.last_attempts_bytes > 34280 and self.last_attempts_bytes <= 109626:
			expected_th = 1.0012 * self.last_attempts_bytes \
						+ 3627.4513 * self.success_ratio \
						- 4812.4582

		elif self.last_attempts_bytes > 72114:
			expected_th = 0.9695 * self.last_attempts_bytes \
						+ 177655.9339 * self.success_ratio \
						- 172464.2645
		else:
			expected_th = 0.748 * self.last_attempts_bytes \
						- 148.9901

		return {'length': 550, 'expected_th': expected_th}

	def mcs0_1024(self):

		expected_th = 0

		if self.last_attempts_bytes > 59774 and self.last_attempts_bytes <= 137836:
			expected_th = 0.8803 * self.last_attempts_bytes \
						+ 1251.5725 * self.success_ratio \
						+ 630.2685 * self.global_channel_utilization \
						- 47500.6259

		elif self.last_attempts_bytes > 99304 and self.last_attempts_bytes <= 176264:
			expected_th = 0.7073 * self.last_attempts_bytes \
						+ 1160.7185 * self.global_channel_utilization \
						- 58284.3375

		elif self.last_attempts_bytes <= 3167.5:
			expected_th = 0.0387 * self.last_attempts_bytes \
						+ 149.9806

		elif self.last_attempts_bytes > 176264:
			expected_th = 1.2983 * self.last_attempts_bytes \
						- 106749.866

		else:
			expected_th = 29160.6202

		return {'length': 1024, 'expected_th': expected_th}

	def mcs0_2048(self):

		expected_th = 0

		if self.last_attempts_bytes > 60172 and self.last_attempts_bytes <= 141607:
			expected_th = 0.9708 * self.last_attempts_bytes \
						+ 1314.4356 * self.success_ratio \
						- 309.4258

		elif self.last_attempts_bytes > 100731:
			expected_th = 0.9471 * self.last_attempts_bytes \
						+ 219434.7577 * self.success_ratio \
						- 208070.1289

		else:
			expected_th = 0.7314 * self.last_attempts_bytes \
						- 59.7816

		return {'length': 2048, 'expected_th': expected_th}

	def mcs0_3839(self):

		expected_th = 0

		if self.last_attempts_bytes > 47705 and self.last_attempts_bytes <= 96999:
			expected_th = -9.9177 * self.last_attempts_bytes \
						+ 0.9247 * self.last_attempts_bytes \
						+ 50918.9539 * self.success_ratio \
						+ 96.9332 * self.global_channel_utilization \
						- 55888.7605

		elif self.last_attempts_bytes > 1811 and self.last_attempts_bytes <= 72065:
			expected_th = -122.5223 * self.last_attempts_bytes \
						+ 0.5664 * self.last_attempts_bytes \
						+ 21077.6124 * self.success_ratio \
						+ 59.8891 * self.global_channel_utilization \
						- 15928.7687

		elif self.last_attempts_bytes <= 49613:
			expected_th = 0.0354 * self.last_attempts_bytes \
						+ 4691.891 * self.success_ratio \
						- 3537.3489

		elif self.last_attempts_bytes <= 201985:
			expected_th = -3311.8903 * self.last_attempts_bytes \
						+ 0.8113 * self.last_attempts_bytes \
						+ 153652.5608 * self.success_ratio \
						- 112970.1392

		elif self.last_attempts_bytes > 241488:
			expected_th = 12263.1968 * self.last_attempts_bytes \
						- 0.1461 * self.last_attempts_bytes \
						+ 260172.3685

		else:
			expected_th = 49801.0357 * self.last_attempts_bytes \
						- 13257.1456

		return {'length': 3839, 'expected_th': expected_th}

	def mcs1_550(self):

		expected_th = 0

		if self.last_attempts_bytes <= 61140:
			expected_th = 84.1163 * self.last_attempts_bytes \
						+ 0.9876 * self.last_attempts_bytes \
						+ 2117.5537 * self.success_ratio \
						- 2744.4491

		elif self.last_attempts_bytes <= 175984:
			expected_th = 10793.0715 * self.last_attempts_bytes \
						+ 0.9584 * self.last_attempts_bytes \
						+ 4868.1258 * self.success_ratio \
						- 93863.7768

		else:
			expected_th = 0.9763 * self.last_attempts_bytes \
						+ 246649.7607 * self.success_ratio \
						- 240885.9307

		return {'length': 550, 'expected_th': expected_th}

	def mcs1_1024(self):

		expected_th = 0

		if self.last_attempts_bytes > 201908:
			expected_th = 0.9743 * self.last_attempts_bytes \
						+ 350566.3588 * self.success_ratio \
						- 341457.277

		elif self.last_attempts_bytes > 3671.5 and self.last_attempts_bytes <= 122032:
			expected_th = 0.968 * self.last_attempts_bytes \
						+ 158696.4981 * self.success_ratio \
						+ 4.7525 * self.global_channel_utilization \
						- 154351.5465

		elif self.last_attempts_bytes <= 3671.5:
			expected_th = 0.0338 * self.last_attempts_bytes \
						+ 265.8779

		else:
			expected_th = 0.8819 * self.last_attempts_bytes \
						+ 5705.4294

		return {'length': 1024, 'expected_th': expected_th}

	def mcs1_2048(self):

		expected_th = 0

		if self.last_attempts_bytes <= 249287:
			expected_th = 0.9885 * self.last_attempts_bytes \
						+ 3297.5379 * self.success_ratio \
						- 3087.9201

		else:
			expected_th = 0.9668 * self.last_attempts_bytes \
						+ 392429.5786 * self.success_ratio \
						- 380089.8137

		return {'length': 2048, 'expected_th': expected_th}

	def mcs1_3839(self):

		expected_th = 0

		if self.last_attempts_bytes > 6642 and self.last_attempts_bytes <= 171535:
			expected_th = 0.9703 * self.last_attempts_bytes \
						+ 115289.3458 * self.success_ratio \
						- 112016.74

		elif self.last_attempts_bytes > 88719 and self.last_attempts_bytes <= 246645:
			expected_th = 0.9601 * self.last_attempts_bytes \
						+ 229655.7694 * self.success_ratio \
						- 220046.0186

		elif self.last_attempts_bytes <= 126274:
			expected_th = 0.038 * self.last_attempts_bytes \
						+ 10033.5784 * self.success_ratio \
						- 8796.3036
			
		elif self.last_attempts_bytes > 395553:
			expected_th = 0.633 * self.last_attempts_bytes \
						+ 1021227.2153 * self.success_ratio \
						- 834029.7453

		else:
			expected_th = 0.8092 * self.last_attempts_bytes \
						+ 301880.9649 * self.success_ratio \
						- 237755.6497

		return {'length': 3839, 'expected_th': expected_th}

	def mcs2_550(self):

		expected_th = 0

		if self.last_attempts_bytes <= 153366 and self.last_attempts_bytes <= 3923.5:
			expected_th = 0.0364 * self.last_attempts_bytes \
						+ 1642.3555 * self.success_ratio \
						- 1373.4996

		elif self.last_attempts_bytes <= 172902:
			expected_th = 421.221 * self.last_attempts_bytes \
						+ 0.9642 * self.last_attempts_bytes \
						- 3531.813

		else:
			expected_th = 34730.6538 * self.last_attempts_bytes \
						+ 0.9891 * self.last_attempts_bytes \
						- 415697.2236

		return {'length': 550, 'expected_th': expected_th}

	def mcs2_1024(self):

		expected_th = 0

		if self.last_attempts_bytes > 3968 and self.last_attempts_bytes > 328917:
			expected_th = 0.9828 * self.last_attempts_bytes \
						+ 430534.8275 * self.success_ratio \
						- 422662.4859

		elif self.last_attempts_bytes <= 3968:
			expected_th = 0.0249 * self.last_attempts_bytes \
						+ 1726.6751 * self.success_ratio \
						- 1433.6429

		elif self.last_attempts_bytes <= 162586:
			expected_th = 0.996 * self.last_attempts_bytes \
						+ 10062.4674 * self.success_ratio \
						- 10072.2468

		elif self.last_attempts_bytes <= 219779:
			expected_th = 0.9895 * self.last_attempts_bytes \
						+ 13692.3711 * self.success_ratio \
						- 12493.2365

		else:
			expected_th = 0.9185 * self.last_attempts_bytes \
						+ 269778.9299 * self.success_ratio \
						- 248366.0629

		return {'length': 1024, 'expected_th': expected_th}

	def mcs2_2048(self):

		expected_th = 0

		if self.last_attempts_bytes <= 302749:
			expected_th = 364.0363 * self.last_attempts_bytes \
						+ 0.9932 * self.last_attempts_bytes \
						- 4332.8353
		else:
			expected_th = 46325.3101 * self.last_attempts_bytes \
						+ 0.9822 * self.last_attempts_bytes \
						- 551094.1685

		return {'length': 2048, 'expected_th': expected_th}

	def mcs2_3839(self):

		expected_th = 0

		if self.last_attempts_bytes > 9704.5 and self.last_attempts_bytes <= 271005:
			expected_th = 0.9755 * self.last_attempts_bytes \
						+ 11749.9738 * self.success_ratio \
						- 11293.0603

		elif self.last_attempts_bytes <= 138609.5:
			expected_th = 0.0348 * self.last_attempts_bytes \
						+ 11113.8254 * self.success_ratio \
						- 10272.1386

		elif self.last_attempts_bytes <= 359310:
			expected_th = 0.9607 * self.last_attempts_bytes \
						+ 316741.2249 * self.success_ratio \
						- 303848.0974
		else:
			expected_th = 0.7431 * self.last_attempts_bytes \
						+ 609286.362 * self.success_ratio \
						- 446990.9487

		return {'length': 3839, 'expected_th': expected_th}

	def mcs3_550(self):

		expected_th = 0.9672 * self.last_attempts_bytes \
					- 4.7476

		return {'length': 550, 'expected_th': expected_th}

	def mcs3_1024(self):

		expected_th = 0

		if self.last_attempts_bytes > 4011 and self.last_attempts_bytes > 296532:
			expected_th = 0.9773 * self.last_attempts_bytes \
						+ 482070.1707 * self.success_ratio \
						- 49.1777 * self.global_channel_utilization \
						- 468461.0774

		else:
			expected_th = 0.9883 * self.last_attempts_bytes \
						+ 98.3863

		return {'length': 1024, 'expected_th': expected_th}

	def mcs3_2048(self):

		expected_th = 0

		if self.last_attempts_bytes > 3489 and self.last_attempts_bytes > 399289:
			expected_th = 0.9842 * self.last_attempts_bytes \
						+ 4.4051 * self.global_channel_utilization \
						+ 1007.3399

		elif self.last_attempts_bytes <= 202128:
			expected_th = 0.0336 * self.last_attempts_bytes \
						+ 5.315 * self.global_channel_utilization \
						- 191.1861

		elif self.last_attempts_bytes <= 799678:
			expected_th = 0.7378 * self.last_attempts_bytes \
						+ 752.755 * self.global_channel_utilization \
						+ 64994.3402

		else:
			expected_th = 1.0624 * self.last_attempts_bytes \
						- 91866.1708

		return {'length': 2048, 'expected_th': expected_th}

	def mcs3_3839(self):

		expected_th = 0

		if self.last_attempts_bytes > 6335 and self.last_attempts_bytes > 299889:
			expected_th = 0.9702 * self.last_attempts_bytes \
						+ 15411.4263 * self.success_ratio \
						- 13454.9991

		elif self.last_attempts_bytes <= 153632:
			expected_th = 0.0321 * self.last_attempts_bytes \
						+ 12046.6541 * self.success_ratio \
						- 11209.1007

		elif self.last_attempts_bytes <= 527511:
			expected_th = 0.9324 * self.last_attempts_bytes \
						+ 439783.4012 * self.success_ratio \
						- 411025.7115

		else:
			expected_th = 0.7903 * self.last_attempts_bytes \
						+ 876479.1705 * self.success_ratio \
						- 716486.5348

		return {'length': 3839, 'expected_th': expected_th}


	def mcs4_550(self):

		expected_th = 0.9485 * self.last_attempts_bytes \
					+ 310.9914

		return {'length': 550, 'expected_th': expected_th}

	def mcs4_1024(self):

		expected_th = 0

		if self.last_attempts_bytes > 199759:
			expected_th = 0.9784 * self.last_attempts_bytes \
						+ 530856.6155 * self.success_ratio \
						- 194.9456 * self.global_channel_utilization \
						- 508980.2825

		elif self.last_attempts_bytes <= 2231.5:
			expected_th = 0.023 * self.last_attempts_bytes \
						+ 1246.484 * self.success_ratio \
						- 996.0992

		elif self.last_attempts_bytes <= 106426:
			expected_th = 0.8624 * self.last_attempts_bytes \
						+ 61669.3648 * self.success_ratio \
						- 53298.0278

		else:
			expected_th = 0.9089 * self.last_attempts_bytes \
						+ 139552.2598 * self.success_ratio \
						- 127232.2565

		return {'length': 1024, 'expected_th': expected_th}

	def mcs4_2048(self):

		expected_th = 0

		if self.last_attempts_bytes > 320550:
			expected_th = 0.9767 * self.last_attempts_bytes \
						+ 611791.206 * self.success_ratio \
						- 596780.9409

		elif self.last_attempts_bytes > 3320:
			expected_th = 0.8957 * self.last_attempts_bytes \
						+ 148562.5908 * self.success_ratio \
						+ 209.4038 * self.global_channel_utilization \
						- 138577.494

		else:
			expected_th = 0.7635 * self.last_attempts_bytes \
						+ 37.7275

		return {'length': 2048, 'expected_th': expected_th}

	def mcs4_3839(self):

		expected_th = 0

		if self.last_attempts_bytes > 142691:
			expected_th = 0.965 * self.last_attempts_bytes \
						+ 678434.223 * self.success_ratio \
						- 656095.0864

		elif self.last_attempts_bytes <= 5740:
			expected_th = 36.7155 * self.last_attempts_bytes \
						+ 0.0316 * self.last_attempts_bytes \
						- 478.5797

		else:
			expected_th = 3898.7353 * self.last_attempts_bytes \
						+ 0.9661 * self.last_attempts_bytes \
						- 75941.1824

		return {'length': 3839, 'expected_th': expected_th}

	def mcs5_550(self):

		expected_th = 0.971 * self.last_attempts_bytes \
					+ 49419.0645 * self.success_ratio \
					- 47274.1827

		return {'length': 550, 'expected_th': expected_th}

	def mcs5_1024(self):

		expected_th = 0

		if self.last_attempts_bytes <= 204548 and self.last_attempts_bytes > 3422:
			expected_th = 0.8859 * self.last_attempts_bytes \
						+ 68974.2735 * self.success_ratio \
						- 58946.9454

		elif self.last_attempts_bytes <= 104356:
			expected_th = 0.0232 * self.last_attempts_bytes \
						+ 6059.0139 * self.success_ratio \
						- 5444.3316

		elif self.last_attempts_bytes <= 458520:
			expected_th = 0.9567 * self.last_attempts_bytes \
						+ 414732.7451 * self.success_ratio \
						- 399890.0929

		else:
			expected_th = 0.9787 * self.last_attempts_bytes \
						+ 692131.8237 * self.success_ratio \
						- 675296.4564

		return {'length': 1024, 'expected_th': expected_th}

	def mcs5_2048(self):

		expected_th = 0

		if self.last_attempts_bytes <= 216869 and self.last_attempts_bytes > 8338:
			expected_th = 0.8225 * self.last_attempts_bytes \
						+ 98160.1931 * self.success_ratio \
						+ 1.0336 * self.global_channel_utilization \
						- 79199.8743

		elif self.last_attempts_bytes > 112423 and self.last_attempts_bytes <= 589758:
			expected_th = 0.9595 * self.last_attempts_bytes \
						+ 847.6563 * self.global_channel_utilization \
						- 40580.1413

		elif self.last_attempts_bytes <= 299784:
			expected_th = 0.0357 * self.last_attempts_bytes \
						+ 211.3386

		else:
			expected_th = 0.994 * self.last_attempts_bytes \
						- 18642.3685

		return {'length': 2048, 'expected_th': expected_th}

	def mcs5_3839(self):

		expected_th = 0

		if self.last_attempts_bytes <= 177938 and self.last_attempts_bytes <= 1908:
			expected_th = 0.0509 * self.last_attempts_bytes \
						+ 7014.5379 * self.success_ratio \
						- 6547.4092

		elif self.last_attempts_bytes <= 479080 and self.last_attempts_bytes > 177938:
			expected_th = -3265.7632 * self.last_attempts_bytes \
						+ 0.9611 * self.last_attempts_bytes \
						+ 346870.5062 * self.success_ratio \
						- 256843.6957

		elif self.last_attempts_bytes <= 327845:
			expected_th = 0.8723 * self.last_attempts_bytes \
						+ 24862.7084 * self.success_ratio \
						+ 6.3024 * self.global_channel_utilization \
						- 19647.0595

		elif self.last_attempts_bytes <= 1246482 and self.last_attempts_bytes > 575707:
			expected_th = 0.8235 * self.last_attempts_bytes \
						+ 843712.515 * self.success_ratio \
						+ 373.814 * self.global_channel_utilization \
						- 737772.9139

		else:
			expected_th = 0.9941 * self.last_attempts_bytes \
						- 7313.4644

		return {'length': 3839, 'expected_th': expected_th}

	def mcs6_550(self):

		expected_th = 0

		if self.last_attempts_bytes <= 61166 and self.last_attempts_bytes > 1627:
			expected_th = 23.4058 * self.last_attempts_bytes \
						+ 1.0016 * self.last_attempts_bytes \
						- 4198.8261

		elif self.last_attempts_bytes <= 31501:
			expected_th = 140.8471 * self.last_attempts_bytes \
						+ 0.0247 * self.last_attempts_bytes \
						- 3368.5203

		elif self.last_attempts_bytes > 300840:
			expected_th = 21186.5374 * self.last_attempts_bytes \
						+ 0.9778 * self.last_attempts_bytes \
						- 532906.3374

		else:
			expected_th = 0.7978 * self.last_attempts_bytes \
						+ 15493.9293

		return {'length': 550, 'expected_th': expected_th}

	def mcs6_1024(self):

		expected_th = 0

		if self.last_attempts_bytes <= 171652 and self.last_attempts_bytes > 3335 and self.last_attempts_bytes <= 8096:
			expected_th = 0.8785 * self.last_attempts_bytes \
						+ 1666.9202 * self.success_ratio \
						- 5162.5654

		elif self.last_attempts_bytes <= 42240:
			expected_th = 0.0237 * self.last_attempts_bytes \
						+ 7147.9122 * self.success_ratio \
						- 6544.7963

		elif self.last_attempts_bytes <= 367548 and self.last_attempts_bytes > 200688:
			expected_th = 9562.3079 * self.last_attempts_bytes \
						+ 0.9623 * self.last_attempts_bytes \
						+ 13913.1298 * self.success_ratio \
						- 248963.4433

		elif self.last_attempts_bytes <= 284111:
			expected_th = 0.9617 * self.last_attempts_bytes \
						+ 16688.7637 * self.success_ratio \
						- 17820.9211

		elif self.last_attempts_bytes <= 926488:
			expected_th = 0.8334 * self.last_attempts_bytes \
						+ 626530.8477 * self.success_ratio \
						- 535139.6843

		else:
			expected_th = 0.9797 * self.last_attempts_bytes \
						+ 4861.3531

		return {'length': 1024, 'expected_th': expected_th}

	def mcs6_2048(self):

		expected_th = 0

		if self.last_attempts_bytes > 161958:
			expected_th = -9260.9131 * self.last_attempts_bytes \
						+ 0.9708 * self.last_attempts_bytes \
						+ 779952.7734 * self.success_ratio \
						- 523359.9254

		elif self.last_attempts_bytes <= 3298:
			expected_th = 0.0308 * self.last_attempts_bytes \
						+ 1726.6335 * self.success_ratio \
						- 2.9828 * self.global_channel_utilization \
						- 1253.645

		elif self.last_attempts_bytes > 100218:
			expected_th = 0.8444 * self.last_attempts_bytes \
						+ 117836.9414 * self.success_ratio \
						+ 5.3214 * self.global_channel_utilization \
						- 99717.4501

		elif self.last_attempts_bytes <= 59476 and self.last_attempts_bytes > 34282:
			expected_th = 0.7344 * self.last_attempts_bytes \
						+ 47363.937 * self.success_ratio \
						- 34965.1629

		elif self.last_attempts_bytes > 60624 and self.success_ratio <= 0.709:
			expected_th = 0.6245 * self.last_attempts_bytes \
						+ 80036.2109 * self.success_ratio \
						- 49914.1271

		elif self.last_attempts_bytes > 46782:
			expected_th = 0.8563 * self.last_attempts_bytes \
						+ 67385.3781 * self.success_ratio \
						- 57890.2951

		else:
			expected_th = 0.6977 * self.last_attempts_bytes \
						+ 1551.5932

		return {'length': 2048, 'expected_th': expected_th}

	def mcs6_3839(self):

		expected_th = 0

		if self.last_attempts_bytes > 122502 and self.last_attempts_bytes <= 582636:
			expected_th = 0.9558 * self.last_attempts_bytes \
						+ 305963.2834 * self.success_ratio \
						+ 56.5189 * self.global_channel_utilization \
						- 295397.3707

		elif self.last_attempts_bytes <= 352543:
			expected_th = 0.9679 * self.last_attempts_bytes \
						+ 10630.9312 * self.success_ratio \
						- 10315.7868

		else:
			expected_th = 0.971 * self.last_attempts_bytes \
						+ 942565.6878 * self.success_ratio \
						+ 281.3889 * self.global_channel_utilization \
						- 930400.2033

		return {'length': 3839, 'expected_th': expected_th}

	def mcs7_550(self):

		expected_th = 0

		if self.last_attempts_bytes <= 71484 and self.last_attempts_bytes > 1790:
			expected_th = 1.006 * self.last_attempts_bytes \
						+ 625.0678 * self.success_ratio \
						+ 2.1483 * self.global_channel_utilization \
						- 4395.3437

		elif self.last_attempts_bytes <= 36911:
			expected_th = 0.0233 * self.last_attempts_bytes \
						+ 2185.3303 * self.success_ratio \
						+ 3.48 * self.global_channel_utilization \
						- 1956.8102

		else:
			expected_th = 0.9629 * self.last_attempts_bytes \
						+ 324594.597 * self.success_ratio \
						+ 373.6267 * self.global_channel_utilization \
						- 320463.531

		return {'length': 550, 'expected_th': expected_th}

	def mcs7_1024(self):

		expected_th = 0

		if self.last_attempts_bytes <= 204300 and self.last_attempts_bytes > 3228:
			expected_th = -28.8594 * self.last_attempts_bytes \
						+ 0.9165 * self.last_attempts_bytes \
						+ 61115.0822 * self.success_ratio \
						- 53038.9563

		elif self.last_attempts_bytes <= 103818:
			expected_th = 0.0246 * self.last_attempts_bytes \
						+ 6875.8503 * self.success_ratio \
						- 6404.1852

		elif self.last_attempts_bytes <= 823228 and self.last_attempts_bytes <= 340236:
			expected_th = -92.5032 * self.last_attempts_bytes \
						+ 0.997 * self.last_attempts_bytes \
						+ 58707.1973 * self.success_ratio \
						- 58475.3998

		else:
			expected_th = -2015.1501 * self.last_attempts_bytes \
						+ 0.9802 * self.last_attempts_bytes \
						+ 705177.8561 * self.success_ratio \
						- 637704.6921

		return {'length': 1024, 'expected_th': expected_th}

	def mcs7_2048(self):

		expected_th = 0

		if self.last_attempts_bytes > 215140:
			expected_th = 0.9847 * self.last_attempts_bytes \
						+ 970053.6998 * self.success_ratio \
						- 958352.4903

		elif self.last_attempts_bytes <= 3307:
			expected_th = 0.0307 * self.last_attempts_bytes \
						+ 1672.7705 * self.success_ratio \
						- 1347.6581

		elif self.last_attempts_bytes <= 105648 and self.last_attempts_bytes > 58342:
			expected_th = 0.7159 * self.last_attempts_bytes \
						+ 71980.7607 * self.success_ratio \
						- 51997.0097

		elif self.last_attempts_bytes > 81994:
			expected_th = 0.9182 * self.last_attempts_bytes \
						+ 132421.7567 * self.success_ratio \
						- 120883.7946

		else:
			expected_th = 0.781 * self.last_attempts_bytes \
						+ 38864.9208 * self.success_ratio \
						- 31018.4872

		return {'length': 2048, 'expected_th': expected_th}

	def mcs7_3839(self):

		expected_th = 0

		if self.last_attempts_bytes <= 150471:
			expected_th = 0.9745 * self.last_attempts_bytes \
						+ 9490.867 * self.success_ratio \
						- 9361.1607

		elif self.last_attempts_bytes <= 700755 and self.last_attempts_bytes > 377093:
			expected_th = 0.9392 * self.last_attempts_bytes \
						+ 604756.0313 * self.success_ratio \
						- 133.5164 * self.global_channel_utilization \
						- 563017.9272

		elif self.last_attempts_bytes <= 537868:
			expected_th = 0.9346 * self.last_attempts_bytes \
						+ 48633.9 * self.success_ratio \
						- 34588.06

		elif self.last_attempts_bytes <= 1111286:
			expected_th = 0.8931 * self.last_attempts_bytes \
						+ 924526.5434 * self.success_ratio \
						- 828108.3156

		else:
			expected_th = 0.9494 * self.last_attempts_bytes \
						+ 1794047.6379 * self.success_ratio \
						- 1708470.0128

		return {'length': 3839, 'expected_th': expected_th}