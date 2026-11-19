"""Benchmark tasks in the style of MBPP (Austin et al., 2021, CC BY 4.0).

Each task has a prompt, assert-based tests, and a reference solution. The
reference solutions exist only so tests/test_evals.py can prove every assertion
is satisfiable; they are never shown to the agent.
"""

TASKS = [
    dict(
        id="remove_occ",
        prompt="Write a function remove_occ(s, ch) that removes the first and last occurrence of character ch from string s.",
        tests=[
            'assert remove_occ("hello", "l") == "heo"',
            'assert remove_occ("abcda", "a") == "bcd"',
            'assert remove_occ("PHP", "P") == "H"',
        ],
        solution='''
def remove_occ(s, ch):
    first = s.find(ch)
    if first == -1:
        return s
    s = s[:first] + s[first + 1:]
    last = s.rfind(ch)
    return s if last == -1 else s[:last] + s[last + 1:]
''',
    ),
    dict(
        id="sort_matrix",
        prompt="Write a function sort_matrix(m) that sorts the rows of a matrix in ascending order of their sums.",
        tests=[
            "assert sort_matrix([[1, 2, 3], [2, 4, 5], [1, 1, 1]]) == [[1, 1, 1], [1, 2, 3], [2, 4, 5]]",
            "assert sort_matrix([[5, 8, 9], [6, 4, 3], [2, 1, 4]]) == [[2, 1, 4], [6, 4, 3], [5, 8, 9]]",
            "assert sort_matrix([[1]]) == [[1]]",
        ],
        solution="def sort_matrix(m):\n    return sorted(m, key=sum)\n",
    ),
    dict(
        id="prism_volume",
        prompt="Write a function prism_volume(l, b, h) that returns the volume of a triangular prism (l * b * h / 2).",
        tests=[
            "assert prism_volume(10, 8, 6) == 240",
            "assert prism_volume(3, 2, 2) == 6",
            "assert prism_volume(1, 2, 1) == 1",
        ],
        solution="def prism_volume(l, b, h):\n    return l * b * h / 2\n",
    ),
    dict(
        id="is_woodall",
        prompt="Write a function is_woodall(n) that returns True if n is a Woodall number (n = k * 2**k - 1 for some k >= 1).",
        tests=[
            "assert is_woodall(383) is True",
            "assert is_woodall(254) is False",
            "assert is_woodall(7) is True",
        ],
        solution='''
def is_woodall(n):
    k = 1
    while k * 2 ** k - 1 <= n:
        if k * 2 ** k - 1 == n:
            return True
        k += 1
    return False
''',
    ),
    dict(
        id="rev_check",
        prompt="Write a function rev_check(n) that returns True if n is one less than twice its digit reversal.",
        tests=[
            "assert rev_check(70) is False",
            "assert rev_check(73) is True",
            "assert rev_check(23) is False",
        ],
        solution="def rev_check(n):\n    return 2 * int(str(n)[::-1]) - 1 == n\n",
    ),
    dict(
        id="find_max_num",
        prompt="Write a function find_max_num(digits) that returns the largest integer that can be formed from a list of digits.",
        tests=[
            "assert find_max_num([1, 2, 3]) == 321",
            "assert find_max_num([4, 5, 6, 1]) == 6541",
            "assert find_max_num([1, 2, 3, 9]) == 9321",
        ],
        solution="def find_max_num(digits):\n    return int(''.join(str(d) for d in sorted(digits, reverse=True)))\n",
    ),
    dict(
        id="opposite_signs",
        prompt="Write a function opposite_signs(a, b) that returns True if two integers have opposite signs.",
        tests=[
            "assert opposite_signs(1, -2) is True",
            "assert opposite_signs(3, 2) is False",
            "assert opposite_signs(-10, -10) is False",
        ],
        solution="def opposite_signs(a, b):\n    return (a < 0) != (b < 0)\n",
    ),
    dict(
        id="octagonal",
        prompt="Write a function octagonal(n) that returns the nth octagonal number (3n^2 - 2n).",
        tests=[
            "assert octagonal(5) == 65",
            "assert octagonal(10) == 280",
            "assert octagonal(15) == 645",
        ],
        solution="def octagonal(n):\n    return 3 * n * n - 2 * n\n",
    ),
    dict(
        id="max_pair_difference",
        prompt="Write a function max_pair_difference(pairs) that returns the maximum absolute difference between the two numbers of any pair in a list of tuples.",
        tests=[
            "assert max_pair_difference([(3, 5), (1, 7), (10, 3), (1, 2)]) == 7",
            "assert max_pair_difference([(4, 6), (2, 17), (9, 13), (11, 12)]) == 15",
            "assert max_pair_difference([(12, 35), (21, 27), (13, 23), (41, 22)]) == 23",
        ],
        solution="def max_pair_difference(pairs):\n    return max(abs(a - b) for a, b in pairs)\n",
    ),
    dict(
        id="recursive_list_sum",
        prompt="Write a function recursive_list_sum(items) that returns the sum of all numbers in an arbitrarily nested list.",
        tests=[
            "assert recursive_list_sum([1, 2, [3, 4], [5, 6]]) == 21",
            "assert recursive_list_sum([7, 10, [15, 14], [19, 41]]) == 106",
            "assert recursive_list_sum([10, [20, [30, [40]]]]) == 100",
        ],
        solution='''
def recursive_list_sum(items):
    return sum(recursive_list_sum(x) if isinstance(x, list) else x for x in items)
''',
    ),
    dict(
        id="pos_count",
        prompt="Write a function pos_count(nums) that counts the positive numbers in a list.",
        tests=[
            "assert pos_count([1, -2, 3, -4]) == 2",
            "assert pos_count([3, 4, 5, -1]) == 3",
            "assert pos_count([0, -1]) == 0",
        ],
        solution="def pos_count(nums):\n    return sum(1 for n in nums if n > 0)\n",
    ),
    dict(
        id="bell_number",
        prompt="Write a function bell_number(n) that returns the nth Bell number (the number of partitions of a set of n elements).",
        tests=[
            "assert bell_number(2) == 2",
            "assert bell_number(4) == 15",
            "assert bell_number(10) == 115975",
        ],
        solution='''
def bell_number(n):
    row = [1]
    for _ in range(n):
        nxt = [row[-1]]
        for value in row:
            nxt.append(nxt[-1] + value)
        row = nxt
    return row[0]
''',
    ),
    dict(
        id="is_monotonic",
        prompt="Write a function is_monotonic(arr) that returns True if the list is entirely non-increasing or non-decreasing.",
        tests=[
            "assert is_monotonic([6, 5, 4, 4]) is True",
            "assert is_monotonic([1, 2, 2, 3]) is True",
            "assert is_monotonic([1, 3, 2]) is False",
        ],
        solution='''
def is_monotonic(arr):
    pairs = list(zip(arr, arr[1:]))
    return all(a <= b for a, b in pairs) or all(a >= b for a, b in pairs)
''',
    ),
    dict(
        id="is_sublist",
        prompt="Write a function is_sublist(items, sub) that returns True if sub appears as a contiguous run inside items.",
        tests=[
            "assert is_sublist([2, 4, 3, 5, 7], [3, 7]) is False",
            "assert is_sublist([2, 4, 3, 5, 7], [4, 3]) is True",
            "assert is_sublist([2, 4, 3, 5, 7], [1, 6]) is False",
        ],
        solution='''
def is_sublist(items, sub):
    n = len(sub)
    return any(items[i:i + n] == sub for i in range(len(items) - n + 1))
''',
    ),
    dict(
        id="comb_sort",
        prompt="Write a function comb_sort(nums) that returns a new list sorted ascending using the comb sort algorithm.",
        tests=[
            "assert comb_sort([5, 15, 37, 25, 79]) == [5, 15, 25, 37, 79]",
            "assert comb_sort([41, 32, 15, 19, 22]) == [15, 19, 22, 32, 41]",
            "assert comb_sort([99, 15, 13, 47]) == [13, 15, 47, 99]",
        ],
        solution='''
def comb_sort(nums):
    nums = list(nums)
    gap, swapped = len(nums), True
    while gap > 1 or swapped:
        gap = max(1, int(gap / 1.3))
        swapped = False
        for i in range(len(nums) - gap):
            if nums[i] > nums[i + gap]:
                nums[i], nums[i + gap] = nums[i + gap], nums[i]
                swapped = True
    return nums
''',
    ),
    dict(
        id="dif_square",
        prompt="Write a function dif_square(n) that returns True if n can be written as the difference of two squares.",
        tests=[
            "assert dif_square(5) is True",
            "assert dif_square(10) is False",
            "assert dif_square(15) is True",
        ],
        solution="def dif_square(n):\n    return n % 4 != 2\n",
    ),
    dict(
        id="find_tuples",
        prompt="Write a function find_tuples(tuples, k) that returns the tuples whose elements are all divisible by k.",
        tests=[
            "assert find_tuples([(6, 24, 12), (7, 9, 6), (12, 18, 21)], 6) == [(6, 24, 12)]",
            "assert find_tuples([(5, 25, 30), (4, 2, 3), (7, 8, 9)], 5) == [(5, 25, 30)]",
            "assert find_tuples([(7, 9, 16), (8, 16, 4), (19, 17, 18)], 4) == [(8, 16, 4)]",
        ],
        solution="def find_tuples(tuples, k):\n    return [t for t in tuples if all(x % k == 0 for x in t)]\n",
    ),
    dict(
        id="is_div_by_11",
        prompt="Write a function is_div_by_11(n) that returns True if n is divisible by 11.",
        tests=[
            "assert is_div_by_11(12345) is False",
            "assert is_div_by_11(1212112) is True",
            "assert is_div_by_11(1212) is False",
        ],
        solution="def is_div_by_11(n):\n    return n % 11 == 0\n",
    ),
    dict(
        id="word_len_odd",
        prompt="Write a function word_len_odd(word) that returns True if the length of the word is odd.",
        tests=[
            'assert word_len_odd("Hadoop") is False',
            'assert word_len_odd("great") is True',
            'assert word_len_odd("structure") is True',
        ],
        solution="def word_len_odd(word):\n    return len(word) % 2 == 1\n",
    ),
    dict(
        id="tetrahedral",
        prompt="Write a function tetrahedral(n) that returns the nth tetrahedral number.",
        tests=[
            "assert tetrahedral(5) == 35",
            "assert tetrahedral(6) == 56",
            "assert tetrahedral(7) == 84",
        ],
        solution="def tetrahedral(n):\n    return n * (n + 1) * (n + 2) // 6\n",
    ),
    dict(
        id="newman_conway",
        prompt="Write a function newman_conway(n) that returns the nth term of the Newman-Conway sequence (P(1) = P(2) = 1, P(n) = P(P(n-1)) + P(n - P(n-1))).",
        tests=[
            "assert newman_conway(10) == 6",
            "assert newman_conway(2) == 1",
            "assert newman_conway(3) == 2",
        ],
        solution='''
def newman_conway(n):
    p = [0, 1, 1]
    for i in range(3, n + 1):
        p.append(p[p[i - 1]] + p[i - p[i - 1]])
    return p[n]
''',
    ),
    dict(
        id="centered_hexagonal",
        prompt="Write a function centered_hexagonal(n) that returns the nth centered hexagonal number.",
        tests=[
            "assert centered_hexagonal(10) == 271",
            "assert centered_hexagonal(2) == 7",
            "assert centered_hexagonal(9) == 217",
        ],
        solution="def centered_hexagonal(n):\n    return 3 * n * (n - 1) + 1\n",
    ),
    dict(
        id="freq_count",
        prompt="Write a function freq_count(items) that returns a dict mapping each element to how many times it appears.",
        tests=[
            "assert freq_count([10, 10, 10, 20]) == {10: 3, 20: 1}",
            "assert freq_count(['a', 'b', 'a']) == {'a': 2, 'b': 1}",
            "assert freq_count([]) == {}",
        ],
        solution='''
def freq_count(items):
    counts = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts
''',
    ),
    dict(
        id="len_longest_word",
        prompt="Write a function len_longest_word(words) that returns the length of the longest word in a list.",
        tests=[
            'assert len_longest_word(["python", "PHP", "bigdata"]) == 7',
            'assert len_longest_word(["a", "ab", "abc"]) == 3',
            'assert len_longest_word(["small", "big", "tall"]) == 5',
        ],
        solution="def len_longest_word(words):\n    return max(len(w) for w in words)\n",
    ),
    dict(
        id="find_substring",
        prompt="Write a function find_substring(strings, sub) that returns True if sub occurs in any string of the list.",
        tests=[
            'assert find_substring(["red", "black", "white", "green", "orange"], "ack") is True',
            'assert find_substring(["red", "black", "white", "green", "orange"], "abc") is False',
            'assert find_substring(["red", "black", "white", "green", "orange"], "ange") is True',
        ],
        solution="def find_substring(strings, sub):\n    return any(sub in s for s in strings)\n",
    ),
    dict(
        id="is_undulating",
        prompt="Write a function is_undulating(n) that returns True if the digits of n alternate between exactly two different digits (at least 3 digits).",
        tests=[
            "assert is_undulating(1212121) is True",
            "assert is_undulating(1991) is False",
            "assert is_undulating(121) is True",
        ],
        solution='''
def is_undulating(n):
    s = str(n)
    return len(s) >= 3 and s[0] != s[1] and all(s[i] == s[i % 2] for i in range(len(s)))
''',
    ),
    dict(
        id="power",
        prompt="Write a function power(a, b) that returns a raised to the power b without using the ** operator or pow().",
        tests=[
            "assert power(3, 4) == 81",
            "assert power(2, 3) == 8",
            "assert power(5, 5) == 3125",
        ],
        solution='''
def power(a, b):
    result = 1
    for _ in range(b):
        result *= a
    return result
''',
    ),
    dict(
        id="index_minimum",
        prompt="Write a function index_minimum(records) that takes a list of (name, value) tuples and returns the name with the smallest value.",
        tests=[
            'assert index_minimum([("Rash", 143), ("Manjeet", 200), ("Varsha", 100)]) == "Varsha"',
            'assert index_minimum([("Yash", 185), ("Dawood", 125), ("Sanya", 175)]) == "Dawood"',
            'assert index_minimum([("Sai", 345), ("Salman", 145), ("Ayesha", 96)]) == "Ayesha"',
        ],
        solution="def index_minimum(records):\n    return min(records, key=lambda r: r[1])[0]\n",
    ),
    dict(
        id="min_length",
        prompt="Write a function min_length(lists) that returns the length of the shortest list in a list of lists.",
        tests=[
            "assert min_length([[1], [1, 2]]) == 1",
            "assert min_length([[1, 2], [1, 2, 3], [1, 2, 3, 4]]) == 2",
            "assert min_length([[3, 3, 3], [4, 4, 4, 4]]) == 3",
        ],
        solution="def min_length(lists):\n    return min(len(x) for x in lists)\n",
    ),
    dict(
        id="divisor_count",
        prompt="Write a function divisor_count(n) that returns the number of positive divisors of n.",
        tests=[
            "assert divisor_count(15) == 4",
            "assert divisor_count(12) == 6",
            "assert divisor_count(9) == 3",
        ],
        solution="def divisor_count(n):\n    return sum(1 for i in range(1, n + 1) if n % i == 0)\n",
    ),
    dict(
        id="flat_frequency",
        prompt="Write a function flat_frequency(lists) that returns a dict counting how often each element appears across a list of lists.",
        tests=[
            "assert flat_frequency([[1, 2, 3, 2], [4, 5, 6, 2], [7, 8, 9, 5]]) == {1: 1, 2: 3, 3: 1, 4: 1, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1}",
            "assert flat_frequency([[1, 1], [1]]) == {1: 3}",
            "assert flat_frequency([[]]) == {}",
        ],
        solution='''
def flat_frequency(lists):
    counts = {}
    for row in lists:
        for item in row:
            counts[item] = counts.get(item, 0) + 1
    return counts
''',
    ),
    dict(
        id="decimal_to_binary",
        prompt="Write a function decimal_to_binary(n) that returns the binary representation of a positive integer as a string, without the '0b' prefix.",
        tests=[
            'assert decimal_to_binary(8) == "1000"',
            'assert decimal_to_binary(18) == "10010"',
            'assert decimal_to_binary(7) == "111"',
        ],
        solution="def decimal_to_binary(n):\n    return format(n, 'b')\n",
    ),
    dict(
        id="next_palindrome",
        prompt="Write a function next_palindrome(n) that returns the smallest palindromic integer strictly greater than n.",
        tests=[
            "assert next_palindrome(99) == 101",
            "assert next_palindrome(1221) == 1331",
            "assert next_palindrome(120) == 121",
        ],
        solution='''
def next_palindrome(n):
    n += 1
    while str(n) != str(n)[::-1]:
        n += 1
    return n
''',
    ),
    dict(
        id="kth_element",
        prompt="Write a function kth_element(arr, k) that returns the kth element of the list using 1-based indexing.",
        tests=[
            "assert kth_element([12, 3, 5, 7, 19], 2) == 3",
            "assert kth_element([17, 24, 8, 23], 3) == 8",
            "assert kth_element([16, 21, 25, 36, 4], 4) == 36",
        ],
        solution="def kth_element(arr, k):\n    return arr[k - 1]\n",
    ),
    dict(
        id="snake_to_camel",
        prompt="Write a function snake_to_camel(s) that converts a snake_case string to UpperCamelCase.",
        tests=[
            'assert snake_to_camel("python_program") == "PythonProgram"',
            'assert snake_to_camel("python_language") == "PythonLanguage"',
            'assert snake_to_camel("programming_language") == "ProgrammingLanguage"',
        ],
        solution="def snake_to_camel(s):\n    return ''.join(part.capitalize() for part in s.split('_'))\n",
    ),
    dict(
        id="eulerian_num",
        prompt="Write a function eulerian_num(n, m) that returns the Eulerian number A(n, m).",
        tests=[
            "assert eulerian_num(3, 1) == 4",
            "assert eulerian_num(4, 1) == 11",
            "assert eulerian_num(5, 3) == 26",
        ],
        solution='''
def eulerian_num(n, m):
    if m >= n or n == 0:
        return 0
    if m == 0:
        return 1
    return (n - m) * eulerian_num(n - 1, m - 1) + (m + 1) * eulerian_num(n - 1, m)
''',
    ),
    dict(
        id="sort_sublists",
        prompt="Write a function sort_sublists(lists) that sorts the strings inside each sublist alphabetically.",
        tests=[
            'assert sort_sublists([["green", "orange"], ["black", "white"], ["white", "black", "orange"]]) == [["green", "orange"], ["black", "white"], ["black", "orange", "white"]]',
            'assert sort_sublists([["b", "a"]]) == [["a", "b"]]',
            "assert sort_sublists([[]]) == [[]]",
        ],
        solution="def sort_sublists(lists):\n    return [sorted(x) for x in lists]\n",
    ),
    dict(
        id="count_true",
        prompt="Write a function count_true(flags) that counts the True values in a list of booleans.",
        tests=[
            "assert count_true([True, False, True]) == 2",
            "assert count_true([False, False]) == 0",
            "assert count_true([True, True, True]) == 3",
        ],
        solution="def count_true(flags):\n    return sum(1 for f in flags if f is True)\n",
    ),
    dict(
        id="add_lists",
        prompt="Write a function add_lists(items, tup) that returns a new tuple made of tup followed by the elements of items.",
        tests=[
            "assert add_lists([5, 6, 7], (9, 10)) == (9, 10, 5, 6, 7)",
            "assert add_lists([6, 7, 8], (10, 11)) == (10, 11, 6, 7, 8)",
            "assert add_lists([], (1,)) == (1,)",
        ],
        solution="def add_lists(items, tup):\n    return tup + tuple(items)\n",
    ),
    dict(
        id="merge_sorted",
        prompt="Write a function merge_sorted(a, b, c) that merges three lists into a single ascending list.",
        tests=[
            "assert merge_sorted([1, 4, 7], [2, 5], [3, 6]) == [1, 2, 3, 4, 5, 6, 7]",
            "assert merge_sorted([25, 24, 15], [19, 20], [11]) == [11, 15, 19, 20, 24, 25]",
            "assert merge_sorted([], [], [1]) == [1]",
        ],
        solution="def merge_sorted(a, b, c):\n    return sorted(a + b + c)\n",
    ),
    dict(
        id="smallest_missing",
        prompt="Write a function smallest_missing(nums) that returns the smallest non-negative integer missing from a sorted list of distinct non-negative integers.",
        tests=[
            "assert smallest_missing([0, 1, 2, 3]) == 4",
            "assert smallest_missing([0, 1, 2, 6, 9]) == 3",
            "assert smallest_missing([2, 3, 5, 8, 9]) == 0",
        ],
        solution='''
def smallest_missing(nums):
    present = set(nums)
    i = 0
    while i in present:
        i += 1
    return i
''',
    ),
    dict(
        id="is_perfect_square",
        prompt="Write a function is_perfect_square(n) that returns True if the non-negative integer n is a perfect square.",
        tests=[
            "assert is_perfect_square(10) is False",
            "assert is_perfect_square(36) is True",
            "assert is_perfect_square(14) is False",
        ],
        solution="import math\n\ndef is_perfect_square(n):\n    return math.isqrt(n) ** 2 == n\n",
    ),
    dict(
        id="is_product_even",
        prompt="Write a function is_product_even(nums) that returns True if the product of the numbers in the list is even.",
        tests=[
            "assert is_product_even([1, 2, 3]) is True",
            "assert is_product_even([1, 2, 1, 4]) is True",
            "assert is_product_even([1, 1]) is False",
        ],
        solution="def is_product_even(nums):\n    return any(n % 2 == 0 for n in nums)\n",
    ),
    dict(
        id="max_sum_list",
        prompt="Write a function max_sum_list(lists) that returns the sublist with the highest sum.",
        tests=[
            "assert max_sum_list([[1, 2, 3], [4, 5, 6], [10, 11, 12], [7, 8, 9]]) == [10, 11, 12]",
            "assert max_sum_list([[3, 2, 1], [6, 5, 4], [12, 11, 10]]) == [12, 11, 10]",
            "assert max_sum_list([[2, 3, 1]]) == [2, 3, 1]",
        ],
        solution="def max_sum_list(lists):\n    return max(lists, key=sum)\n",
    ),
    dict(
        id="max_run_uppercase",
        prompt="Write a function max_run_uppercase(s) that returns the length of the longest run of consecutive uppercase letters in s.",
        tests=[
            'assert max_run_uppercase("GeMKSForGERksISBESt") == 5',
            'assert max_run_uppercase("PrECIOusMOVemENTSYT") == 6',
            'assert max_run_uppercase("GooGLEFluTTER") == 4',
        ],
        solution='''
def max_run_uppercase(s):
    best = run = 0
    for ch in s:
        run = run + 1 if ch.isupper() else 0
        best = max(best, run)
    return best
''',
    ),
    dict(
        id="first_odd",
        prompt="Write a function first_odd(nums) that returns the first odd number in a list.",
        tests=[
            "assert first_odd([1, 3, 5]) == 1",
            "assert first_odd([2, 4, 1, 3]) == 1",
            "assert first_odd([8, 9, 1]) == 9",
        ],
        solution="def first_odd(nums):\n    return next(n for n in nums if n % 2 == 1)\n",
    ),
    dict(
        id="check_k",
        prompt="Write a function check_k(tup, k) that returns True if the tuple contains k.",
        tests=[
            "assert check_k((10, 4, 5, 6, 8), 6) is True",
            "assert check_k((1, 2, 3, 4, 5, 6), 7) is False",
            "assert check_k((7, 8, 9, 44, 11, 12), 11) is True",
        ],
        solution="def check_k(tup, k):\n    return k in tup\n",
    ),
    dict(
        id="check_smaller",
        prompt="Write a function check_smaller(t1, t2) that returns True if every element of t2 is smaller than the element at the same index in t1.",
        tests=[
            "assert check_smaller((1, 2, 3), (2, 3, 4)) is False",
            "assert check_smaller((4, 5, 6), (3, 4, 5)) is True",
            "assert check_smaller((11, 12, 13), (10, 11, 12)) is True",
        ],
        solution="def check_smaller(t1, t2):\n    return all(b < a for a, b in zip(t1, t2))\n",
    ),
    dict(
        id="remove_odd_chars",
        prompt="Write a function remove_odd_chars(s) that removes the characters at odd positions (1st, 3rd, 5th, ...) and returns the rest.",
        tests=[
            'assert remove_odd_chars("python") == "yhn"',
            'assert remove_odd_chars("program") == "rga"',
            'assert remove_odd_chars("language") == "agae"',
        ],
        solution="def remove_odd_chars(s):\n    return s[1::2]\n",
    ),
    dict(
        id="second_smallest",
        prompt="Write a function second_smallest(nums) that returns the second smallest distinct value in the list, or None if there is none.",
        tests=[
            "assert second_smallest([1, 2, -8, -2, 0, -2]) == -2",
            "assert second_smallest([1, 1, -0.5, 0, 2, -2, -2]) == -0.5",
            "assert second_smallest([2, 2]) is None",
        ],
        solution='''
def second_smallest(nums):
    distinct = sorted(set(nums))
    return distinct[1] if len(distinct) > 1 else None
''',
    ),
    dict(
        id="count_char_position",
        prompt="Write a function count_char_position(s) that counts the letters that sit at the same position as in the English alphabet (case-insensitive, 'a' at index 0).",
        tests=[
            'assert count_char_position("xbcefg") == 2',
            'assert count_char_position("ABcED") == 3',
            'assert count_char_position("AbgdeF") == 5',
        ],
        solution='''
def count_char_position(s):
    return sum(1 for i, ch in enumerate(s.lower()) if ord(ch) - ord("a") == i)
''',
    ),
]
