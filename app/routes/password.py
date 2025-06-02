from werkzeug.security import generate_password_hash, check_password_hash

def create(password):
    return generate_password_hash(password)

# print(create('Linhxinh2@2'))
print(check_password_hash('scrypt:32768:8:1$B02yzewcVoP9hTJ3$0c7c536d4d1357f1f7afa74adaa80287824aeaeddfa9e176976c63450606961f3d10c1a5be7e0ca8e2ce4dc053bd25fad47c0b442c41736d3be28f7f58fbc1e7', 'Linhxinh2@2'))