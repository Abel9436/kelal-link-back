ALPHABET = "ሀለሐመሠረሰሸቀበተቸኀነኘአከኸወዐዘዠየደጀገጠጨጰጸፀፈፐ"
BASE = len(ALPHABET)

def encode(num: int) -> str:
    if num == 0:
        return ALPHABET[0]
    
    arr = []
    while num:
        num, rem = divmod(num, BASE)
        arr.append(ALPHABET[rem])
    
    arr.reverse()
    return "".join(arr)

def decode(slug: str) -> int:
    num = 0
    for char in slug:
        num = num * BASE + ALPHABET.index(char)
    return num
