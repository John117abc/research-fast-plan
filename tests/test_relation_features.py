from relation_features import relationize_exact_row


ego_extent = [2.2, 0.9, 0.7]

# 1. 前方静止物体，自车 10 m/s：应该正在接近，未来最小余量下降
row_stationary = [1, 20.0, 0.0, 0.0, 0.0, 1.8, 4.4]
r1 = relationize_exact_row(row_stationary, 10.0, ego_extent)
assert r1[3] > 0.0, r1                    # closing > 0
assert r1[2] < r1[1], r1                  # min margin < current margin
assert r1[5] > 0.99 and abs(r1[6]) < 1e-3 # bearing 向正前方

# 2. 前车同速同向：closing 应接近 0，未来最小余量不明显恶化
row_same_speed = [1, 20.0, 0.0, 0.0, 36.0, 1.8, 4.4]
r2 = relationize_exact_row(row_same_speed, 10.0, ego_extent)
assert abs(r2[3]) < 1e-5, r2
assert abs(r2[2] - r2[1]) < 1e-5, r2

# 3. 右侧/侧向对象：bearing 的 sin 不应为 0
row_side = [1, 10.0, -10.0, 90.0, 36.0, 1.8, 4.4]
r3 = relationize_exact_row(row_side, 10.0, ego_extent)
assert abs(r3[6]) > 0.1, r3

print('All relation feature tests passed.')
print('stationary:', r1)
print('same speed:', r2)
print('side:', r3)
