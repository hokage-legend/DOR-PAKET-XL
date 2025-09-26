from app.client.engsel import get_family
from app.service.auth import AuthInstance

def get_packages_by_family_data(family_code: str, is_enterprise: bool, tokens: dict):
    """
    Mengambil dan memformat data paket dari family code.
    Fungsi ini sekarang menerima 'tokens' secara langsung untuk mendukung multi-user.
    """
    # Guard clause untuk memastikan token ada
    if not tokens:
        print("Error: get_packages_by_family_data dipanggil tanpa token.")
        return []

    # Gunakan api_key dari AuthInstance dan tokens yang diberikan dari main.py
    family_data = get_family(AuthInstance.api_key, tokens, family_code, is_enterprise)
    
    if not family_data or "package_variants" not in family_data:
        return []

    all_options = []
    # Loop melalui semua variant dan option untuk mengumpulkan paket
    for variant in family_data.get("package_variants", []):
        for option in variant.get("package_options", []):
            formatted_option = {
                "number": option.get("order"),
                "variant_name": variant.get("name"),
                "option_name": option.get("name"),
                "price": option.get("price"),
                "code": option.get("package_option_code"),
                "option_order": option.get("order"),
                # Tambahkan data penting lainnya yang mungkin dibutuhkan oleh bookmark
                "family_code": family_code,
                "is_enterprise": is_enterprise,
                "family_name": family_data.get("package_family", {}).get("name")
            }
            all_options.append(formatted_option)

    # Urutkan semua paket yang ditemukan berdasarkan nomor urutnya
    all_options.sort(key=lambda x: x.get("number", 0))
    
    # Beri nomor ulang dari 1 agar tampilan di bot selalu urut
    for i, option in enumerate(all_options):
        option["number"] = i + 1

    return all_options