import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:km_marketplace/core/l10n/app_localizations.dart';

import '../../../../app/theme.dart';

class ListingCard extends StatelessWidget {
  const ListingCard({
    super.key,
    required this.id,
    required this.title,
    required this.price,
    required this.currency,
    required this.city,
    required this.transactionType,
    this.thumbnailUrl,
    this.isFavorite = false,
    this.isPromoted = false,
    this.onTap,
    this.onFavoriteTap,
  });

  final int id;
  final String title;
  final double price;
  final String currency;
  final String city;
  final String transactionType;
  final String? thumbnailUrl;
  final bool isFavorite;
  final bool isPromoted;
  final VoidCallback? onTap;
  final VoidCallback? onFavoriteTap;

  String get _formattedPrice {
    final intPrice = price.toInt();
    final buffer = StringBuffer();
    final str = intPrice.toString();
    for (var i = 0; i < str.length; i++) {
      if (i > 0 && (str.length - i) % 3 == 0) buffer.write(' ');
      buffer.write(str[i]);
    }
    return '$buffer $currency';
  }

  String _transactionLabel(S l) {
    switch (transactionType) {
      case 'sale':
        return l.sale;
      case 'rent_long':
        return l.rentLong;
      case 'rent_daily':
        return l.rentDaily;
      default:
        return transactionType;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = S.of(context)!;
    final shortPromotionLabel =
        Localizations.localeOf(context).languageCode == 'ru' ? 'про.' : 'pro.';

    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.bgSurface,
          borderRadius: BorderRadius.circular(AppTheme.cardRadius),
          border: Border.all(color: AppTheme.border),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image
            AspectRatio(
              aspectRatio: 16 / 10,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  if (thumbnailUrl != null)
                    CachedNetworkImage(
                      imageUrl: thumbnailUrl!,
                      fit: BoxFit.cover,
                      placeholder: (context, url) =>
                          Container(color: AppTheme.bgMuted),
                      errorWidget: (context, url, error) => Container(
                        color: AppTheme.bgMuted,
                        child: const Icon(
                          Icons.image_not_supported_outlined,
                          color: AppTheme.textSubtle,
                          size: 32,
                        ),
                      ),
                    )
                  else
                    Container(
                      color: AppTheme.bgMuted,
                      child: const Icon(
                        Icons.apartment_rounded,
                        color: AppTheme.textSubtle,
                        size: 40,
                      ),
                    ),
                  // Transaction type badge
                  Positioned(
                    top: 8,
                    left: 8,
                    right: 46,
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: AppTheme.accent.withValues(alpha: 0.9),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          _transactionLabel(l),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ),
                  if (isPromoted)
                    Positioned(
                      left: 8,
                      bottom: 8,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: AppTheme.statusSuccess,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(
                              Icons.bolt,
                              size: 11,
                              color: Colors.white,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              shortPromotionLabel,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  // Favorite button
                  Positioned(
                    top: 6,
                    right: 6,
                    child: Material(
                      color: Colors.transparent,
                      child: InkWell(
                        onTap: onFavoriteTap,
                        customBorder: const CircleBorder(),
                        child: Container(
                          padding: const EdgeInsets.all(6),
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.35),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            isFavorite
                                ? Icons.bookmark
                                : Icons.bookmark_outline,
                            color: isFavorite
                                ? AppTheme.bookmarkActive
                                : Colors.white,
                            size: 20,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            // Info
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _formattedPrice,
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.textMain,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 14,
                      color: AppTheme.textMain,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      const Icon(
                        Icons.location_on_outlined,
                        size: 14,
                        color: AppTheme.textSubtle,
                      ),
                      const SizedBox(width: 3),
                      Expanded(
                        child: Text(
                          city,
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.textSubtle,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
