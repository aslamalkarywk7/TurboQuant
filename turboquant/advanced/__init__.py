"""advanced — نظام الخوارزميات المتقدمة (lossless دائماً).

المكونات:
- entropy: بوابة الإنتروبيا (تخزين خام للعشوائي بدل حرق CPU).
- bwt: تحويل Burrows-Wheeler بأسلوب bzip2.
- delta: فروقات byte/16-bit/XOR للمتسلسلات.
- filters: مرشحات تنبؤية بأسلوب PNG.
- zdict: قواميس zstd ذاتية التدريب.
- pipeline: المنسق الذكي (تحليل → سباق → تنفيذ).

الاستخدام:
    import turboquant as tq
    tq.compress_lossless("data.csv", "data.tqz", mode="max", advanced=True)
    tq.analyze_file("data.csv")  # تقرير قبل الضغط
"""
from __future__ import annotations

from .entropy import byte_entropy, analyze, COMPRESSIBLE_MAX, INCOMPRESSIBLE_MIN
from .delta import (delta8_encode, delta8_decode, xor8_encode, xor8_decode,
                    delta16le_encode, delta16le_decode, xor_with)
from .bwt import bwt_encode, bwt_decode, bwt_encode_block, bwt_decode_block, BLOCK_SIZE
from .filters import filters_encode, filters_decode, STRIDE_CANDIDATES
from .zdict import train_dict, dict_compress, dict_decompress, self_train, pack_body, unpack_body
from .pipeline import (TRANSFORMS, ADV_CAP, SELECT_CAP, CANDIDATES_BY_KIND,
                       apply_transform, invert_transform, smart_select, analyze_file)

__all__ = [
    "byte_entropy", "analyze",
    "delta8_encode", "delta8_decode", "xor8_encode", "xor8_decode",
    "delta16le_encode", "delta16le_decode", "xor_with",
    "bwt_encode", "bwt_decode",
    "filters_encode", "filters_decode",
    "train_dict", "dict_compress", "dict_decompress", "self_train",
    "TRANSFORMS", "ADV_CAP", "apply_transform", "invert_transform",
    "smart_select", "analyze_file",
]
