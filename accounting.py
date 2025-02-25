import csv

# 入力データ
apple_price = 100
orange_price = 50
apple_count = 2
orange_count = 3
coupon_value = 20
coupon_count = 2

# 計算処理
total_price = (apple_price * apple_count) + (orange_price * orange_count) - (coupon_value * coupon_count)

# 結果の出力
output_path = './output.csv'
with open(output_path, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['計算結果'])
    writer.writerow([total_price])